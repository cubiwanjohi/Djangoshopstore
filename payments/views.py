
"""M-Pesa payment callback views."""

import json
import logging
from decimal import Decimal, InvalidOperation

from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from inventory.models import StockMovement
from inventory.services import record_stock_movement
from store.models import Payment, Product


logger = logging.getLogger(__name__)

FROM_EMAIL = 'shop@example.com'


def _extract_callback_payment_details(callback):
    """Extract and validate payment amount and M-Pesa receipt number."""
    metadata = callback.get('CallbackMetadata')

    if not isinstance(metadata, dict):
        return None, ''

    items = metadata.get('Item')

    if not isinstance(items, list):
        return None, ''

    amount_value = None
    receipt_value = None

    for item in items:
        if not isinstance(item, dict):
            continue

        if item.get('Name') == 'Amount':
            amount_value = item.get('Value')

        elif item.get('Name') == 'MpesaReceiptNumber':
            receipt_value = item.get('Value')

    if amount_value is None:
        return None, ''

    try:
        amount = Decimal(str(amount_value))
    except (InvalidOperation, TypeError, ValueError):
        return None, ''

    if not amount.is_finite():
        return None, ''

    receipt = (
        receipt_value.strip()
        if isinstance(receipt_value, str)
        else ''
    )

    if not receipt or len(receipt) > 30:
        return amount, ''

    return amount, receipt


def _restore_payment_stock(order):
    """Restore reserved stock and record returned movements."""
    for item in order.items.select_related('product'):
        Product.objects.filter(pk=item.product_id).update(
            stock=F('stock') + item.quantity
        )

        record_stock_movement(
            product=item.product,
            order=order,
            movement_type=StockMovement.MovementType.RETURNED,
            quantity=item.quantity,
            note='Stock returned after failed M-Pesa payment',
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
            logger.warning(
                'M-Pesa callback for unknown CheckoutRequestID'
            )

        elif payment.status != 'pending':
            logger.info(
                'Ignoring repeated callback for payment %s',
                payment.pk,
            )

        elif result_code == 0:
            callback_amount, receipt_number = (
                _extract_callback_payment_details(callback)
            )

            if callback_amount is None or not receipt_number:
                logger.warning(
                    'M-Pesa success callback missing valid amount '
                    'or receipt for payment %s',
                    payment.pk,
                )

            elif callback_amount != payment.amount:
                logger.warning(
                    'M-Pesa amount mismatch for payment %s: '
                    'expected %s, received %s',
                    payment.pk,
                    payment.amount,
                    callback_amount,
                )

            else:
                payment.status = 'completed'
                payment.mpesa_receipt_number = receipt_number
                payment.save(
                    update_fields=[
                        'status',
                        'mpesa_receipt_number',
                    ]
                )

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
