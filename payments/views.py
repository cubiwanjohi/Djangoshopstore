"""M-Pesa payment callback views."""

import json
import logging
from decimal import Decimal, InvalidOperation

import requests
from django.core import signing
from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from inventory.services import restore_reserved_stock
from notifications.services import send_payment_confirmation
from payments.services.mpesa import stk_push_query
from store.models import Payment
logger = logging.getLogger(__name__)

def _extract_callback_payment_details(callback):
    """Extract and validate payment amount and M-Pesa receipt number."""
    metadata = callback.get("CallbackMetadata")

    if not isinstance(metadata, dict):
        return None, ""

    items = metadata.get("Item")

    if not isinstance(items, list):
        return None, ""

    amount_value = None
    receipt_value = None

    for item in items:
        if not isinstance(item, dict):
            continue

        if item.get("Name") == "Amount":
            amount_value = item.get("Value")
        elif item.get("Name") == "MpesaReceiptNumber":
            receipt_value = item.get("Value")

    if amount_value is None:
        return None, ""

    try:
        amount = Decimal(str(amount_value))
    except (InvalidOperation, TypeError, ValueError):
        return None, ""

    if not amount.is_finite() or amount < 0:
        return None, ""

    receipt = (
        receipt_value.strip()
        if isinstance(receipt_value, str)
        else ""
    )

    if not receipt or len(receipt) > 30:
        return amount, ""

    return amount, receipt

def _parse_result_code(value):
    """Return a valid integer result code, or None."""
    if isinstance(value, bool):
        return None

    if not isinstance(value, (int, str)):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def _restore_payment_stock(order):
    """Restore outstanding stock reservations after failed payment."""
    return restore_reserved_stock(
        order=order,
        note="Stock returned after failed M-Pesa payment",
    )

def _query_confirms_callback(checkout_request_id, callback_result_code):
    """
    Independently verify the callback outcome using Daraja STK Push Query.

    A query request being accepted is not enough. The returned checkout ID
    and transaction result code must also match the callback.
    """
    try:
        result = stk_push_query(checkout_request_id)
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning(
            "M-Pesa query failed for CheckoutRequestID %s: %s",
            checkout_request_id,
            exc,
        )
        return False

    if not isinstance(result, dict):
        logger.warning("Invalid M-Pesa query response structure")
        return False

    response_code = _parse_result_code(result.get("ResponseCode"))
    query_result_code = _parse_result_code(result.get("ResultCode"))
    query_checkout_id = result.get("CheckoutRequestID")

    if response_code != 0:
        logger.warning(
            "M-Pesa query was not accepted for CheckoutRequestID %s",
            checkout_request_id,
        )
        return False

    if query_checkout_id != checkout_request_id:
        logger.warning(
            "M-Pesa query CheckoutRequestID mismatch"
        )
        return False

    if query_result_code is None:
        logger.warning(
            "M-Pesa query did not provide a valid transaction result"
        )
        return False

    if query_result_code != callback_result_code:
        logger.warning(
            "M-Pesa query result does not match callback for %s",
            checkout_request_id,
        )
        return False

    return True

@csrf_exempt
@require_POST
def mpesa_callback(request):
    """Process Safaricom's asynchronous STK Push callback."""

    # 1. Validate callback payload.
    try:
        payload = json.loads(request.body)

        if not isinstance(payload, dict):
            raise ValueError("Invalid callback payload structure")

        body = payload.get("Body")

        if not isinstance(body, dict):
            raise ValueError("Invalid callback Body")

        callback = body.get("stkCallback")

        if not isinstance(callback, dict):
            raise ValueError("Invalid stkCallback")

        checkout_request_id = callback.get("CheckoutRequestID")

        if not isinstance(checkout_request_id, str):
            raise ValueError("Missing CheckoutRequestID")

        checkout_request_id = checkout_request_id.strip()

        if not checkout_request_id:
            raise ValueError("Empty CheckoutRequestID")

        result_code = _parse_result_code(callback.get("ResultCode"))

        if result_code is None:
            raise ValueError("Invalid ResultCode")

    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        logger.warning("Malformed M-Pesa callback received")

        return JsonResponse(
            {
                "ResultCode": 1,
                "ResultDesc": "Invalid payload",
            },
            status=400,
        )

    # 2. Check whether this payment exists and is still pending.
    payment_status = Payment.objects.filter(
        transaction_id=checkout_request_id
    ).values_list("status", flat=True).first()

    if payment_status is None:
        logger.warning(
            "M-Pesa callback for unknown CheckoutRequestID"
        )
        return JsonResponse(
            {"ResultCode": 0, "ResultDesc": "Accepted"}
        )

    if payment_status != "pending":
        logger.info(
            "Ignoring repeated callback for CheckoutRequestID %s",
            checkout_request_id,
        )
        return JsonResponse(
            {"ResultCode": 0, "ResultDesc": "Accepted"}
        )

    # 3. Verify the transaction with Safaricom before changing the database.
    if not _query_confirms_callback(
        checkout_request_id,
        result_code,
    ):
        return JsonResponse(
            {"ResultCode": 0, "ResultDesc": "Accepted"}
        )

    # 4. Validate successful callback metadata.
    callback_amount = None
    receipt_number = ""

    if result_code == 0:
        callback_amount, receipt_number = (
            _extract_callback_payment_details(callback)
        )

        if callback_amount is None or not receipt_number:
            logger.warning(
                "M-Pesa success callback missing valid amount "
                "or receipt for CheckoutRequestID %s",
                checkout_request_id,
            )
            return JsonResponse(
                {"ResultCode": 0, "ResultDesc": "Accepted"}
            )

    # 5. Lock the payment and process it atomically.
    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .filter(transaction_id=checkout_request_id)
            .first()
        )

        if payment is None:
            logger.warning(
                "Payment disappeared during M-Pesa callback processing"
            )

        elif payment.status != "pending":
            logger.info(
                "Payment %s was already processed",
                payment.pk,
            )

        elif result_code == 0:
            if callback_amount != payment.amount:
                logger.warning(
                    "M-Pesa amount mismatch for payment %s: "
                    "expected %s, received %s",
                    payment.pk,
                    payment.amount,
                    callback_amount,
                )
            else:
                payment.status = "completed"
                payment.mpesa_receipt_number = receipt_number

                payment.save(
                    update_fields=[
                        "status",
                        "mpesa_receipt_number",
                    ]
                )

                payment.order.status = "paid"
                payment.order.save(update_fields=["status"])

                transaction.on_commit(
                    lambda order_id=payment.order_id:
                        send_payment_confirmation(order_id)
                )

        else:
            payment.status = "failed"
            payment.save(update_fields=["status"])

            _restore_payment_stock(payment.order)

    # 6. Acknowledge callback.
    return JsonResponse(
        {"ResultCode": 0, "ResultDesc": "Accepted"}
    )

@require_GET
def payment_status(request, token):
    """
    Return the current payment status using a signed order-access token.

    The token supports guest checkout without exposing payment records
    through predictable order IDs.
    """
    try:
        data = signing.loads(
            token,
            salt="payments.order-status",
            max_age=86400,
        )
    except signing.BadSignature:
        return JsonResponse(
            {"error": "Invalid or expired payment link."},
            status=404,
        )

    # Only accept a dictionary containing a valid integer order ID.
    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "Invalid payment link."},
            status=404,
        )

    order_id = data.get("order_id")

    if not isinstance(order_id, int) or isinstance(order_id, bool):
        return JsonResponse(
            {"error": "Invalid payment link."},
            status=404,
        )

    payment = Payment.objects.filter(
        order_id=order_id
    ).values("status").first()

    if payment is None:
        return JsonResponse(
            {"error": "Payment not found."},
            status=404,
        )

    response = JsonResponse({
        "status": payment["status"],
    })
    response["Cache-Control"] = "no-store"
    return response
