"""Automated tests for the storefront: catalogue, cart, checkout and M-Pesa callback.

The M-Pesa network call (store.views.stk_push) is always mocked, so these tests
never contact Safaricom and never move money.
"""

import json
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from .models import Order, OrderItem, Payment, Product
from .views import _normalize_phone

STK_OK = {
    'ResponseCode': '0',
    'CheckoutRequestID': 'ws_CO_TEST_001',
    'CustomerMessage': 'Success. Request accepted for processing',
}

VALID_FORM = {
    'name': 'Jane Wanjiru',
    'email': 'jane@example.com',
    'address': '12 Kenyatta Avenue',
    'city': 'Nairobi',
    'phone': '0712345678',
    'mpesa_phone': '0712345678',
}


def make_product(**overrides):
    values = {'name': 'Coffee', 'price': Decimal('300'), 'stock': 10}
    values.update(overrides)
    return Product.objects.create(**values)


def put_in_cart(client, product, quantity=1):
    """Place a product in the client's session cart without going through the views."""
    session = client.session
    cart = session.get('cart', {})
    cart[str(product.pk)] = quantity
    session['cart'] = cart
    session.save()


# --------------------------------------------------------------------------
# Helpers and models
# --------------------------------------------------------------------------

class NormalizePhoneTests(SimpleTestCase):
    def test_accepts_common_safaricom_formats(self):
        accepted = {
            '0712345678': '254712345678',
            '0112345678': '254112345678',
            '+254712345678': '254712345678',
            '254712345678': '254712345678',
            '712345678': '254712345678',
            '0712 345 678': '254712345678',
            '+254 712-345-678': '254712345678',
        }
        for raw, expected in accepted.items():
            with self.subTest(raw=raw):
                self.assertEqual(_normalize_phone(raw), expected)

    def test_rejects_invalid_numbers(self):
        for raw in (None, '', '12345', '0612345678', '25471234567', '07123456789', 'abcdefghij'):
            with self.subTest(raw=raw):
                self.assertIsNone(_normalize_phone(raw))


class OrderModelTests(TestCase):
    def test_total_sums_price_times_quantity_for_every_item(self):
        order = Order.objects.create(
            customer_name='Jane',
            customer_email='jane@example.com',
            shipping_address='12 Kenyatta Avenue',
            shipping_city='Nairobi',
            shipping_phone='0712345678',
        )
        coffee = make_product(name='Coffee', price=Decimal('300'))
        flowers = make_product(name='Flowers', price=Decimal('50'))
        OrderItem.objects.create(order=order, product=coffee, quantity=2, price=coffee.price)
        OrderItem.objects.create(order=order, product=flowers, quantity=3, price=flowers.price)

        self.assertEqual(order.total(), Decimal('750'))


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------

class CatalogueTests(TestCase):
    def test_product_list_shows_prices_in_ksh(self):
        make_product(price=Decimal('300'))
        response = self.client.get(reverse('product_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'KSh 300')
        self.assertNotContains(response, '$')

    def test_product_list_flags_low_and_missing_stock(self):
        make_product(name='Low', stock=3)
        make_product(name='Gone', stock=0)
        response = self.client.get(reverse('product_list'))

        self.assertContains(response, 'Only 3 left')
        self.assertContains(response, 'Out of stock')

    def test_product_detail_returns_404_for_unknown_product(self):
        response = self.client.get(reverse('product_detail', args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_header_shows_number_of_items_in_cart(self):
        product = make_product()
        put_in_cart(self.client, product, 2)
        response = self.client.get(reverse('product_list'))

        self.assertEqual(response.context['cart_count'], 2)


# --------------------------------------------------------------------------
# Cart
# --------------------------------------------------------------------------

class CartTests(TestCase):
    def setUp(self):
        self.product = make_product(stock=2)
        self.add_url = reverse('cart_add', args=[self.product.pk])

    def test_adding_a_product_stores_it_in_the_session_and_shows_the_cart(self):
        response = self.client.post(self.add_url)

        self.assertRedirects(response, reverse('cart_view'))
        self.assertEqual(self.client.session['cart'], {str(self.product.pk): 1})

    def test_adding_the_same_product_again_increases_the_quantity(self):
        self.client.post(self.add_url)
        self.client.post(self.add_url)

        self.assertEqual(self.client.session['cart'], {str(self.product.pk): 2})

    def test_quantity_never_exceeds_available_stock(self):
        for _ in range(5):
            self.client.post(self.add_url)

        self.assertEqual(self.client.session['cart'], {str(self.product.pk): 2})

    def test_out_of_stock_product_cannot_be_added(self):
        self.product.stock = 0
        self.product.save()
        self.client.post(self.add_url)

        self.assertEqual(self.client.session.get('cart', {}), {})

    def test_adding_requires_post(self):
        response = self.client.get(self.add_url)
        self.assertEqual(response.status_code, 405)

    def test_adding_an_unknown_product_returns_404(self):
        response = self.client.post(reverse('cart_add', args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_cart_page_shows_lines_and_total(self):
        self.client.post(self.add_url)
        self.client.post(self.add_url)
        response = self.client.get(reverse('cart_view'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['items']), 1)
        self.assertEqual(response.context['total'], Decimal('600'))
        self.assertContains(response, 'KSh 600')

    def test_cart_ignores_products_that_no_longer_exist(self):
        session = self.client.session
        session['cart'] = {'999': 1}
        session.save()
        response = self.client.get(reverse('cart_view'))

        self.assertEqual(response.context['items'], [])
        self.assertContains(response, 'Your cart is empty')


# --------------------------------------------------------------------------
# Checkout
# --------------------------------------------------------------------------

class CheckoutTests(TestCase):
    def setUp(self):
        self.product = make_product(stock=10, price=Decimal('300'))
        self.url = reverse('checkout')

        patcher = mock.patch('store.views.stk_push', return_value=dict(STK_OK))
        self.stk_push = patcher.start()
        self.addCleanup(patcher.stop)

    # --- viewing the form ---

    def test_empty_cart_redirects_to_the_shop(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse('product_list'))

    def test_form_shows_order_summary(self):
        put_in_cart(self.client, self.product, 2)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total'], Decimal('600'))
        self.assertContains(response, 'Pay KSh 600')

    # --- a successful order ---

    def test_successful_checkout_creates_order_items_and_pending_payment(self):
        put_in_cart(self.client, self.product, 2)
        response = self.client.post(self.url, VALID_FORM)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/order_success.html')
        self.assertTrue(response.context['payment_prompt_sent'])

        order = Order.objects.get()
        self.assertEqual(order.customer_name, 'Jane Wanjiru')
        self.assertEqual(order.customer_email, 'jane@example.com')
        self.assertEqual(order.shipping_city, 'Nairobi')
        self.assertEqual(order.status, 'pending')

        item = order.items.get()
        self.assertEqual(item.product, self.product)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.price, Decimal('300'))

        payment = order.payment
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(payment.amount, Decimal('600'))
        self.assertEqual(payment.mpesa_phone, '254712345678')
        self.assertEqual(payment.transaction_id, 'ws_CO_TEST_001')

    def test_checkout_asks_safaricom_for_the_right_amount_and_number(self):
        put_in_cart(self.client, self.product, 2)
        self.client.post(self.url, VALID_FORM)

        self.stk_push.assert_called_once()
        kwargs = self.stk_push.call_args.kwargs
        order = Order.objects.get()
        self.assertEqual(kwargs['phone_number'], '254712345678')
        self.assertEqual(kwargs['amount'], Decimal('600'))
        self.assertEqual(kwargs['account_reference'], f'Order{order.id}')

    def test_checkout_reserves_stock_and_empties_the_cart(self):
        put_in_cart(self.client, self.product, 3)
        self.client.post(self.url, VALID_FORM)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)
        self.assertEqual(self.client.session['cart'], {})

    def test_checkout_sends_a_confirmation_email(self):
        put_in_cart(self.client, self.product)
        self.client.post(self.url, VALID_FORM)

        order = Order.objects.get()
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['jane@example.com'])
        self.assertIn(f'#{order.id}', mail.outbox[0].subject)
        self.assertIn('KSh 300', mail.outbox[0].body)

    def test_different_phone_formats_are_normalised(self):
        for raw in ('0712345678', '+254712345678', '712345678'):
            with self.subTest(raw=raw):
                put_in_cart(self.client, self.product)
                self.client.post(self.url, {**VALID_FORM, 'mpesa_phone': raw})
                payment = Payment.objects.latest('id')
                self.assertEqual(payment.mpesa_phone, '254712345678')

    # --- validation ---

    def assert_rejected(self, response, expected_error=None):
        """The order was refused: error shown, nothing created, stock and cart untouched."""
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'store/checkout.html')
        self.assertIn('error', response.context)
        if expected_error:
            self.assertIn(expected_error, response.context['error'])
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)
        self.stk_push.assert_not_called()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)
        self.assertTrue(self.client.session['cart'])

    def test_every_required_field_must_be_filled_in(self):
        for field in ('name', 'email', 'address', 'city', 'phone', 'mpesa_phone'):
            with self.subTest(field=field):
                put_in_cart(self.client, self.product)
                response = self.client.post(self.url, {**VALID_FORM, field: ''})
                self.assert_rejected(response)

    def test_fields_containing_only_spaces_are_rejected(self):
        put_in_cart(self.client, self.product)
        response = self.client.post(self.url, {**VALID_FORM, 'name': '   '})
        self.assert_rejected(response, 'fill in all the fields')

    def test_invalid_email_is_rejected(self):
        put_in_cart(self.client, self.product)
        response = self.client.post(self.url, {**VALID_FORM, 'email': 'not-an-email'})
        self.assert_rejected(response, 'valid email')

    def test_invalid_mpesa_number_is_rejected(self):
        for bad in ('12345', '0612345678', 'abcdefghij'):
            with self.subTest(number=bad):
                put_in_cart(self.client, self.product)
                response = self.client.post(self.url, {**VALID_FORM, 'mpesa_phone': bad})
                self.assert_rejected(response, 'Safaricom number')

    def test_over_long_fields_are_rejected(self):
        put_in_cart(self.client, self.product)
        response = self.client.post(self.url, {**VALID_FORM, 'name': 'x' * 201})
        self.assert_rejected(response, 'too long')

    def test_form_keeps_what_the_customer_typed_after_an_error(self):
        put_in_cart(self.client, self.product)
        response = self.client.post(self.url, {**VALID_FORM, 'email': 'not-an-email'})

        self.assertContains(response, 'value="Jane Wanjiru"')
        self.assertContains(response, 'value="12 Kenyatta Avenue"')

    # --- stock ---

    def test_ordering_more_than_the_stock_is_refused(self):
        self.product.stock = 2
        self.product.save()
        put_in_cart(self.client, self.product, 5)
        response = self.client.post(self.url, VALID_FORM)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['error'],
            'Sorry, "Coffee" does not have enough stock.',
        )
        self.assertEqual(Order.objects.count(), 0)
        self.stk_push.assert_not_called()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)

    def test_one_unavailable_item_cancels_the_whole_order(self):
        flowers = make_product(name='Flowers', price=Decimal('50'), stock=1)
        put_in_cart(self.client, self.product, 1)   # available
        put_in_cart(self.client, flowers, 3)         # only 1 in stock
        response = self.client.post(self.url, VALID_FORM)

        self.assertContains(response, 'does not have enough stock')
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.product.refresh_from_db()
        flowers.refresh_from_db()
        self.assertEqual(self.product.stock, 10)   # the available item was rolled back too
        self.assertEqual(flowers.stock, 1)

    # --- M-Pesa problems ---

    def test_rejected_prompt_marks_the_payment_failed_and_returns_the_stock(self):
        self.stk_push.return_value = {'ResponseCode': '1', 'errorMessage': 'Bad request'}
        put_in_cart(self.client, self.product, 3)
        with self.assertLogs('store.views', level='WARNING'):
            response = self.client.post(self.url, VALID_FORM)

        payment = Payment.objects.get()
        self.assertEqual(payment.status, 'failed')
        self.assertEqual(payment.transaction_id, '')
        self.assertFalse(response.context['payment_prompt_sent'])
        self.assertContains(response, 'could not start the M-Pesa payment')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_network_error_while_contacting_safaricom_is_handled(self):
        self.stk_push.side_effect = ConnectionError('network down')
        put_in_cart(self.client, self.product, 2)
        with self.assertLogs('store.views', level='ERROR'):
            response = self.client.post(self.url, VALID_FORM)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.get().status, 'failed')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 10)

    def test_success_response_without_a_request_id_counts_as_failed(self):
        self.stk_push.return_value = {'ResponseCode': '0'}
        put_in_cart(self.client, self.product)
        with self.assertLogs('store.views', level='WARNING'):
            self.client.post(self.url, VALID_FORM)

        self.assertEqual(Payment.objects.get().status, 'failed')


# --------------------------------------------------------------------------
# M-Pesa callback
# --------------------------------------------------------------------------

def callback_payload(checkout_request_id='ws_CO_TEST_001', result_code=0):
    return {
        'Body': {
            'stkCallback': {
                'MerchantRequestID': 'merchant-1',
                'CheckoutRequestID': checkout_request_id,
                'ResultCode': result_code,
                'ResultDesc': 'Result description from Safaricom',
            }
        }
    }


class MpesaCallbackTests(TestCase):
    def setUp(self):
        # Stock is 8 because 2 of the 10 units are reserved by the pending order.
        self.product = make_product(stock=8)
        self.order = Order.objects.create(
            customer_name='Jane Wanjiru',
            customer_email='jane@example.com',
            shipping_address='12 Kenyatta Avenue',
            shipping_city='Nairobi',
            shipping_phone='0712345678',
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, quantity=2, price=self.product.price
        )
        self.payment = Payment.objects.create(
            order=self.order,
            method='mpesa',
            amount=Decimal('600'),
            mpesa_phone='254712345678',
            transaction_id='ws_CO_TEST_001',
        )
        self.url = reverse('mpesa_callback')

    def post_json(self, payload, client=None):
        return (client or self.client).post(
            self.url, data=json.dumps(payload), content_type='application/json'
        )

    def refresh(self):
        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.product.refresh_from_db()

    # --- success ---

    def test_successful_payment_marks_payment_completed_and_order_paid(self):
        response = self.post_json(callback_payload(result_code=0))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ResultCode': 0, 'ResultDesc': 'Accepted'})
        self.refresh()
        self.assertEqual(self.payment.status, 'completed')
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.product.stock, 8)

    def test_successful_payment_emails_the_customer(self):
        self.post_json(callback_payload(result_code=0))

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['jane@example.com'])
        self.assertIn('Payment received', mail.outbox[0].subject)

    # --- failure ---

    def test_cancelled_payment_marks_it_failed_and_returns_the_stock(self):
        response = self.post_json(callback_payload(result_code=1032))

        self.assertEqual(response.status_code, 200)
        self.refresh()
        self.assertEqual(self.payment.status, 'failed')
        self.assertEqual(self.order.status, 'pending')
        self.assertEqual(self.product.stock, 10)
        self.assertEqual(len(mail.outbox), 0)

    # --- repeated callbacks ---

    def test_repeated_success_callback_is_processed_once(self):
        self.post_json(callback_payload(result_code=0))
        response = self.post_json(callback_payload(result_code=0))

        self.assertEqual(response.status_code, 200)
        self.refresh()
        self.assertEqual(self.payment.status, 'completed')
        self.assertEqual(len(mail.outbox), 1)

    def test_a_late_failure_cannot_undo_a_completed_payment(self):
        self.post_json(callback_payload(result_code=0))
        self.post_json(callback_payload(result_code=1032))

        self.refresh()
        self.assertEqual(self.payment.status, 'completed')
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.product.stock, 8)

    def test_repeated_failure_callback_returns_the_stock_only_once(self):
        self.post_json(callback_payload(result_code=1032))
        self.post_json(callback_payload(result_code=1032))

        self.refresh()
        self.assertEqual(self.product.stock, 10)

    # --- unexpected input ---

    def test_unknown_request_id_changes_nothing(self):
        with self.assertLogs('store.views', level='WARNING'):
            response = self.post_json(callback_payload(checkout_request_id='ws_CO_UNKNOWN'))

        self.assertEqual(response.status_code, 200)
        self.refresh()
        self.assertEqual(self.payment.status, 'pending')
        self.assertEqual(self.order.status, 'pending')

    def test_malformed_payloads_are_rejected_with_400(self):
        bad_payloads = {
            'not json': 'this is not json',
            'empty object': '{}',
            'missing stkCallback': json.dumps({'Body': {}}),
            'null body': json.dumps({'Body': None}),
            'a list': '[]',
            'missing result code': json.dumps(
                {'Body': {'stkCallback': {'CheckoutRequestID': 'ws_CO_TEST_001'}}}
            ),
            'non-numeric result code': json.dumps(callback_payload(result_code='abc')),
        }
        for label, body in bad_payloads.items():
            with self.subTest(payload=label):
                with self.assertLogs('store.views', level='WARNING'):
                    response = self.client.post(
                        self.url, data=body, content_type='application/json'
                    )
                self.assertEqual(response.status_code, 400)
                self.refresh()
                self.assertEqual(self.payment.status, 'pending')

    def test_get_requests_are_not_allowed(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_callback_does_not_need_a_csrf_token(self):
        # Safaricom's servers cannot send a CSRF token, so the endpoint is exempt.
        strict_client = Client(enforce_csrf_checks=True)
        response = self.post_json(callback_payload(result_code=0), client=strict_client)

        self.assertEqual(response.status_code, 200)
        self.refresh()
        self.assertEqual(self.payment.status, 'completed')