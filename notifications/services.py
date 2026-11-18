
"""Reusable customer email notification services."""

import logging

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail import send_mail
from django.template.loader import render_to_string

from store.models import Order, Payment

logger = logging.getLogger(__name__)

FROM_EMAIL = getattr(
    settings,
    "DEFAULT_FROM_EMAIL",
    "shop@example.com",
)


def send_customer_notification(
    subject,
    template_name,
    context,
    recipient,
):
    """Send an email without interrupting shop operations."""
    if not recipient:
        logger.warning(
            "Cannot send notification '%s': missing recipient.",
            subject,
        )
        return False

    try:
        message = render_to_string(
            template_name,
            context,
        )

        send_mail(
            subject=subject,
            message=message,
            from_email=FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )

        logger.info(
            "Notification sent: %s to %s",
            subject,
            recipient,
        )
        return True

    except Exception:
        logger.exception(
            "Failed to send notification '%s' to %s",
            subject,
            recipient,
        )
        return False


def send_order_confirmation(order_id, payment_prompt_sent):
    """Notify a customer that their order was received."""
    try:
        order = Order.objects.get(pk=order_id)
    except ObjectDoesNotExist:
        logger.warning("Order not found: %s", order_id)
        return False

    return send_customer_notification(
        subject=f"Order #{order.id} received",
        template_name="notifications/emails/order_confirmation.txt",
        context={
            "order": order,
            "payment_prompt_sent": payment_prompt_sent,
        },
        recipient=order.customer_email,
    )


def send_payment_confirmation(order_id):
    """Notify a customer after successful M-Pesa verification."""
    try:
        order = Order.objects.get(pk=order_id)
        payment = Payment.objects.get(order=order)
    except ObjectDoesNotExist:
        logger.warning(
            "Payment confirmation skipped: order or payment %s not found.",
            order_id,
        )
        return False

    if payment.status != "completed":
        logger.warning(
            "Payment confirmation skipped for unpaid order %s",
            order_id,
        )
        return False

    return send_customer_notification(
        subject=f"Payment confirmed for order #{order.id}",
        template_name="notifications/emails/payment_confirmation.txt",
        context={
            "order": order,
            "payment": payment,
        },
        recipient=order.customer_email,
    )


def send_order_shipped_notification(order_id):
    """Notify a customer that their order has been dispatched."""
    try:
        order = Order.objects.get(pk=order_id)
    except ObjectDoesNotExist:
        logger.warning("Order not found: %s", order_id)
        return False

    if order.delivery_status != "shipped":
        return False

    return send_customer_notification(
        subject=f"Order #{order.id} dispatched",
        template_name="notifications/emails/order_shipped.txt",
        context={"order": order},
        recipient=order.customer_email,
    )


def send_order_delivered_notification(order_id):
    """Notify a customer that their order has been delivered."""
    try:
        order = Order.objects.get(pk=order_id)
    except ObjectDoesNotExist:
        logger.warning("Order not found: %s", order_id)
        return False

    if order.delivery_status != "delivered":
        return False

    return send_customer_notification(
        subject=f"Order #{order.id} delivered",
        template_name="notifications/emails/order_delivered.txt",
        context={"order": order},
        recipient=order.customer_email,
    )
