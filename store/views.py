
"""Storefront views: catalogue, cart, checkout and the M-Pesa callback."""

import logging
import re

from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Order, OrderItem, Payment, Product
from payments.services.mpesa import stk_push

logger = logging.getLogger(__name__)

FROM_EMAIL = 'shop@example.com'


class OutOfStock(Exception):
    """Raised during checkout when a product cannot cover the requested quantity."""

    def __init__(self, product_name):
        super().__init__(product_name)
        self.product_name = product_name


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _normalize_phone(raw):
    """Return a Safaricom number as 2547XXXXXXXX / 2541XXXXXXXX, or None if invalid."""
    digits = re.sub(r'\D', '', raw or '')
    if digits.startswith('254') and len(digits) == 12:
        national = digits[3:]
    elif digits.startswith('0') and len(digits) == 10:
        national = digits[1:]
    elif len(digits) == 9:
        national = digits
    else:
        return None

    if national[0] not in '17':
        return None

    return '254' + national


def _cart_lines(request):
    """Resolve the session cart into line items, skipping products that no longer exist."""
    cart = request.session.get('cart', {})
    ids = [int(pk) for pk in cart if str(pk).isdigit()]
    products = Product.objects.in_bulk(ids)

    lines, total = [], 0
    for pk, qty in cart.items():
        product = products.get(int(pk)) if str(pk).isdigit() else None
        if product is None:
            continue

        subtotal = product.price * qty
        total += subtotal
        lines.append({
            'product': product,
            'quantity': qty,
            'subtotal': subtotal,
        })

    return lines, total


def _restore_stock(order):
    """Return an order's reserved stock to inventory (used when payment fails)."""
    for item in order.items.all():
        Product.objects.filter(pk=item.product_id).update(
            stock=F('stock') + item.quantity
        )


def _send_email(subject, message, recipient):
    """Send an email without ever breaking the request if the mail backend fails."""
    try:
        send_mail(subject, message, FROM_EMAIL, [recipient], fail_silently=False)
    except Exception:
        logger.exception('Failed to send email: %s', subject)


# --------------------------------------------------------------------------
# Catalogue
# --------------------------------------------------------------------------

def product_list(request):
    products = Product.objects.all()
    return render(request, 'store/product_list.html', {'products': products})


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'store/product_detail.html', {'product': product})


# --------------------------------------------------------------------------
# Cart
# --------------------------------------------------------------------------

@require_POST
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = request.session.get('cart', {})
    key = str(product.pk)

    if cart.get(key, 0) < product.stock:
        cart[key] = cart.get(key, 0) + 1
        request.session['cart'] = cart

    return redirect('cart_view')


def cart_view(request):
    items, total = _cart_lines(request)
    return render(request, 'store/cart.html', {
        'items': items,
        'total': total,
    })


# --------------------------------------------------------------------------
# Checkout
# --------------------------------------------------------------------------

def checkout(request):
    lines, total = _cart_lines(request)

    if not lines:
        return redirect('product_list')

    context = {
        'items': lines,
        'total': total,
        'form': request.POST,
    }

    if request.method != 'POST':
        return render(request, 'store/checkout.html', context)

    name = request.POST.get('name', '').strip()
    email = request.POST.get('email', '').strip()
    address = request.POST.get('address', '').strip()
    city = request.POST.get('city', '').strip()
    phone = request.POST.get('phone', '').strip()
    mpesa_phone = _normalize_phone(request.POST.get('mpesa_phone'))

    error = None

    if not all([name, email, address, city, phone]):
        error = 'Please fill in all the fields.'
    elif (
        len(name) > 200
        or len(address) > 255
        or len(city) > 100
        or len(phone) > 20
    ):
        error = 'One of the fields is too long.'
    elif mpesa_phone is None:
        error = 'Enter a valid Safaricom number, for example 0712345678.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            error = 'Enter a valid email address.'

    if error:
        return render(
            request,
            'store/checkout.html',
            {**context, 'error': error},
        )

    # Create the order, reserve stock and record the pending payment atomically.
    try:
        with transaction.atomic():
            product_ids = [line['product'].pk for line in lines]

            locked = {
                p.pk: p
                for p in Product.objects.select_for_update().filter(
                    pk__in=product_ids
                )
            }

            # Associate the order with the logged-in customer.
            # Guest orders will have user=None.
            order = Order.objects.create(
                user=request.user if request.user.is_authenticated else None,
                customer_name=name,
                customer_email=email,
                shipping_address=address,
                shipping_city=city,
                shipping_phone=phone,
            )

            for line in lines:
                product = locked.get(line['product'].pk)
                qty = line['quantity']

                if product is None or product.stock < qty:
                    raise OutOfStock(line['product'].name)

                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=qty,
                    price=product.price,
                )

                Product.objects.filter(pk=product.pk).update(
                    stock=F('stock') - qty
                )

            payment = Payment.objects.create(
                order=order,
                method='mpesa',
                amount=order.total(),
                mpesa_phone=mpesa_phone,
            )

    except OutOfStock as exc:
        return render(
            request,
            'store/checkout.html',
            {
                **context,
                'error': (
                    f'Sorry, "{exc.product_name}" '
                    'does not have enough stock.'
                ),
            },
        )

    # Ask Safaricom to prompt the customer. This network call runs
    # outside the database transaction.
    prompt_sent = False
    checkout_request_id = ''

    try:
        stk_response = stk_push(
            phone_number=mpesa_phone,
            amount=payment.amount,
            account_reference=f'Order{order.id}',
            transaction_desc=f'Payment for Order #{order.id}',
        )

        checkout_request_id = stk_response.get('CheckoutRequestID', '')

        prompt_sent = (
            str(stk_response.get('ResponseCode')) == '0'
            and bool(checkout_request_id)
        )

        if not prompt_sent:
            logger.warning(
                'STK push rejected for order %s: %s',
                order.id,
                stk_response,
            )

    except Exception:
        logger.exception('STK push failed for order %s', order.id)

    if prompt_sent:
        payment.transaction_id = checkout_request_id
        payment.save(update_fields=['transaction_id'])

    else:
        with transaction.atomic():
            payment.status = 'failed'
            payment.save(update_fields=['status'])
            _restore_stock(order)

    request.session['cart'] = {}

    if prompt_sent:
        payment_line = (
            'Enter your M-Pesa PIN on your phone to complete the payment.'
        )
    else:
        payment_line = (
            'We could not start the M-Pesa payment. '
            'Please contact us about this order.'
        )

    _send_email(
        subject=f'Order #{order.id} received',
        message=(
            f'Hi {order.customer_name},\n\n'
            f'Thanks for your order! Order #{order.id} '
            f'total: KSh {order.total()}\n'
            f'Delivery to: {order.shipping_address}, '
            f'{order.shipping_city}\n\n'
            f'{payment_line}'
        ),
        recipient=order.customer_email,
    )

    return render(
        request,
        'store/order_success.html',
        {
            'order': order,
            'payment': payment,
            'payment_prompt_sent': prompt_sent,
        },
    )


# --------------------------------------------------------------------------
# M-Pesa callback
# --------------------------------------------------------------------------
