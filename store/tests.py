
import json
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from .models import Product, Order, OrderItem, Payment


class ProductModelTests(TestCase):
    """Test Product model behavior."""

    def setUp(self):
        self.product = Product.objects.create(
            name="Laptop",
            description="A test laptop",
            price=Decimal("75000.00"),
            stock=10,
        )

    def test_product_creation(self):
        self.assertEqual(self.product.name, "Laptop")
        self.assertEqual(self.product.price, Decimal("75000.00"))
        self.assertEqual(self.product.stock, 10)

    def test_product_string_representation(self):
        self.assertEqual(str(self.product), "Laptop")

    def test_product_default_stock(self):
        product = Product.objects.create(
            name="Mouse",
            price=Decimal("1500.00"),
        )
        self.assertEqual(product.stock, 0)

    def test_product_get_absolute_url(self):
        self.assertEqual(
            self.product.get_absolute_url(),
            reverse("product_detail", args=[self.product.pk]),
        )


class OrderModelTests(TestCase):
    """Test order totals and default statuses."""

    def setUp(self):
        self.product = Product.objects.create(
            name="Keyboard",
            price=Decimal("2500.00"),
            stock=20,
        )

        self.order = Order.objects.create(
            customer_name="Peter",
            customer_email="peter@example.com",
            shipping_address="Kerugoya Road",
            shipping_city="Kerugoya",
            shipping_phone="0712345678",
        )

    def test_order_default_statuses(self):
        self.assertEqual(self.order.status, "pending")
        self.assertEqual(self.order.delivery_status, "processing")

    def test_order_total(self):
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal("2500.00"),
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=3,
            price=Decimal("100.00"),
        )

        self.assertEqual(self.order.total(), Decimal("5300.00"))

    def test_order_item_subtotal(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=3,
            price=Decimal("2500.00"),
        )

        self.assertEqual(item.subtotal(), Decimal("7500.00"))

    def test_deleting_order_deletes_order_items(self):
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price=Decimal("2500.00"),
        )
        item_id = item.pk

        self.order.delete()

        self.assertFalse(
            OrderItem.objects.filter(pk=item_id).exists()
        )


class PaymentModelTests(TestCase):
    """Test payment creation and defaults."""

    def setUp(self):
        self.order = Order.objects.create(
            customer_name="Peter",
            customer_email="peter@example.com",
        )

    def test_payment_creation(self):
        payment = Payment.objects.create(
            order=self.order,
            amount=Decimal("5000.00"),
            mpesa_phone="254712345678",
        )

        self.assertEqual(payment.method, "mpesa")
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.amount, Decimal("5000.00"))
        self.assertEqual(
            str(payment),
            f"Payment for Order #{self.order.pk} - pending",
        )

    def test_payment_has_one_order(self):
        Payment.objects.create(
            order=self.order,
            amount=Decimal("1000.00"),
        )

        # A OneToOneField permits only one Payment per Order.
        with self.assertRaises(Exception):
            Payment.objects.create(
                order=self.order,
                amount=Decimal("2000.00"),
            )


class StoreViewTests(TestCase):
    """Test product and cart views."""

    def setUp(self):
        self.product = Product.objects.create(
            name="Phone",
            description="Test phone",
            price=Decimal("12000.00"),
            stock=5,
        )

    def test_product_list_page(self):
        response = self.client.get(reverse("product_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Phone")

    def test_product_detail_page(self):
        response = self.client.get(
            reverse("product_detail", args=[self.product.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Phone")

    def test_product_detail_returns_404_for_missing_product(self):
        response = self.client.get(
            reverse("product_detail", args=[99999])
        )

        self.assertEqual(response.status_code, 404)

    def test_cart_add_increases_quantity(self):
        url = reverse("cart_add", args=[self.product.pk])

        # The cart_add view requires POST requests.
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("cart_view"))

        cart = self.client.session.get("cart", {})
        self.assertEqual(cart[str(self.product.pk)], 1)

        # Adding the same product again increases its quantity.
        response = self.client.post(url)

        self.assertEqual(response.status_code, 302)

        cart = self.client.session.get("cart", {})
        self.assertEqual(cart[str(self.product.pk)], 2)

    def test_cart_view_calculates_total(self):
        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

        response = self.client.get(reverse("cart_view"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["total"],
            Decimal("24000.00"),
        )

    def test_empty_checkout_page(self):
        # An empty cart redirects to the product catalogue.
        response = self.client.get(reverse("checkout"))

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            reverse("product_list"),
        )


class CheckoutTests(TestCase):
    """Test checkout without contacting the real M-Pesa service."""

    def setUp(self):
        self.product = Product.objects.create(
            name="Headphones",
            price=Decimal("2000.00"),
            stock=10,
        )

        session = self.client.session
        session["cart"] = {str(self.product.pk): 2}
        session.save()

    @patch("store.views.send_mail")
    @patch("store.views.stk_push")
    def test_checkout_creates_order_and_payment(
        self, mock_stk_push, mock_send_mail
    ):
        mock_stk_push.return_value = {
            "CheckoutRequestID": "TEST-CHECKOUT-123",
            "ResponseCode": "0",
            "ResponseDescription": "Success",
        }

        response = self.client.post(
            reverse("checkout"),
            {
                "name": "Peter",
                "email": "peter@example.com",
                "address": "Kerugoya Road",
                "city": "Kerugoya",
                "phone": "0712345678",
                "mpesa_phone": "0712345678",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

        order = Order.objects.get()
        payment = Payment.objects.get()

        self.assertEqual(order.customer_name, "Peter")
        self.assertEqual(order.total(), Decimal("4000.00"))
        self.assertEqual(payment.amount, Decimal("4000.00"))
        self.assertEqual(payment.mpesa_phone, "254712345678")
        self.assertEqual(
            payment.transaction_id,
            "TEST-CHECKOUT-123",
        )

        self.assertEqual(self.client.session["cart"], {})
        mock_stk_push.assert_called_once()
        mock_send_mail.assert_called_once()


class MpesaCallbackTests(TestCase):
    """Test successful and failed M-Pesa callbacks."""

    def setUp(self):
        self.order = Order.objects.create(
            customer_name="Peter",
            customer_email="peter@example.com",
        )

        self.payment = Payment.objects.create(
            order=self.order,
            amount=Decimal("3000.00"),
            transaction_id="TEST-CHECKOUT-456",
        )

    def send_callback(self, result_code):
        payload = {
            "Body": {
                "stkCallback": {
                    "CheckoutRequestID": "TEST-CHECKOUT-456",
                    "ResultCode": result_code,
                    "ResultDesc": "Test result",
                }
            }
        }

        return self.client.post(
            reverse("mpesa_callback"),
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_successful_callback_marks_order_paid(self):
        response = self.send_callback(0)

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.status, "completed")
        self.assertEqual(self.order.status, "paid")

    def test_failed_callback_marks_payment_failed(self):
        response = self.send_callback(1)

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.payment.status, "failed")
        self.assertEqual(self.order.status, "pending")
