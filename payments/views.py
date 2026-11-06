"""M-Pesa payment callback views."""

import json
import logging

from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from store.models import Payment, Product

logger = logging.getLogger(__name__)

FROM_EMAIL = 'shop@example.com'


def _restore_payment_stock(order):
    """Restore reserved product stock when an M-Pesa payment fails."""
    for item in order.items.all():
        Product.objects.filter(pk=item.product_id).update(
            stock=F('stock') + item.quantity
        )


def _send_payment_email(subject, message, recipient):
    """Send a payment email without breaking the callback if email fails."""
    try:
        send_mail(
            subject,
            message,
            FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Failed to send payment email: %s', subject)


@csrf_exempt
@require_POST
def mpesa_callback(request):
    """Process Safaricom's asynchronous STK Push callback."""

    try:
        callback = json.loads(request.body)['Body']['stkCallback']
        checkout_request_id = callback['CheckoutRequestID']
        result_code = int(callback['ResultCode'])

    except (ValueError, KeyError, TypeError):
        logger.warning('Malformed M-Pesa callback received')
        return JsonResponse(
            {'ResultCode': 1, 'ResultDesc': 'Invalid payload'},
            status=400,
        )

    paid_order = None

    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .filter(transaction_id=checkout_request_id)
            .first()
        )

        if payment is None:
            logger.warning('M-Pesa callback for unknown CheckoutRequestID')

        elif payment.status != 'pending':
            logger.info(
                'Ignoring repeated callback for payment %s',
                payment.pk,
            )

        elif result_code == 0:
            payment.status = 'completed'
            payment.save(update_fields=['status'])

            payment.order.status = 'paid'
            payment.order.save(update_fields=['status'])

            paid_order = payment.order

        else:
            payment.status = 'failed'
            payment.save(update_fields=['status'])
            _restore_payment_stock(payment.order)

    if paid_order is not None:
        _send_payment_email(
            subject=f'Payment received for order #{paid_order.id}',
            message=(
                f'Hi {paid_order.customer_name},\n\n'
                f'We have received your M-Pesa payment of '
                f'KSh {paid_order.total()} for order #{paid_order.id}.\n'
                f'Delivery to: {paid_order.shipping_address}, '
                f'{paid_order.shipping_city}\n\n'
                "We'll notify you when it ships."
            ),
            recipient=paid_order.customer_email,
        )

    return JsonResponse(
        {'ResultCode': 0, 'ResultDesc': 'Accepted'}
    )