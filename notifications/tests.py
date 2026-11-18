
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings

from store.models import Order, OrderItem, Payment, Product

from .services import (
    send_customer_notification,
    send_order_confirmation,
    send_order_delivered_notification,
    send_order_shipped_notification,
    send_payment_confirmation,
)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="shop@example.com",
)
class NotificationServiceTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            name="Test Product",
            description="A product for notification tests",
            price=Decimal("600.00"),
            stock=10,
        )

        self.order = Order.objects.create(
            customer_name="Test Customer",
            customer_email="customer@example.com",
            shipping_address="123 Test Street",
            shipping_city="Nairobi",
            shipping_phone="0712345678",
        )

        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price=Decimal("600.00"),
        )

        self.payment = Payment.objects.create(
            order=self.order,
            amount=Decimal("600.00"),
            mpesa_phone="254712345678",
            transaction_id="TEST-CHECKOUT-ID",
        )

    def test_order_confirmation_email_is_sent(self):
        result = send_order_confirmation(
            self.order.id,
            payment_prompt_sent=True,
        )

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            f"Order #{self.order.id} received",
        )
        self.assertEqual(
            mail.outbox[0].to,
            ["customer@example.com"],
        )
        self.assertIn(
            "Test Customer",
            mail.outbox[0].body,
        )
        self.assertIn(
            "M-Pesa payment request has been sent",
            mail.outbox[0].body,
        )

    def test_payment_confirmation_email_is_sent(self):
        self.payment.status = "completed"
        self.payment.mpesa_receipt_number = "ABC123XYZ"
        self.payment.save()

        result = send_payment_confirmation(self.order.id)

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            f"Payment confirmed for order #{self.order.id}",
        )
        self.assertIn(
            "ABC123XYZ",
            mail.outbox[0].body,
        )

    def test_payment_confirmation_is_not_sent_for_pending_payment(self):
        result = send_payment_confirmation(self.order.id)

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)

    def test_order_shipped_email_includes_tracking_number(self):
        self.order.delivery_status = "shipped"
        self.order.tracking_number = "SHOP-TRACK-123"
        self.order.save()

        result = send_order_shipped_notification(self.order.id)

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            f"Order #{self.order.id} dispatched",
        )
        self.assertIn(
            "SHOP-TRACK-123",
            mail.outbox[0].body,
        )

    def test_shipped_email_is_not_sent_for_processing_order(self):
        result = send_order_shipped_notification(self.order.id)

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)

    def test_order_delivered_email_is_sent(self):
        self.order.delivery_status = "delivered"
        self.order.save()

        result = send_order_delivered_notification(self.order.id)

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(
            mail.outbox[0].subject,
            f"Order #{self.order.id} delivered",
        )
        self.assertIn(
            "successfully delivered",
            mail.outbox[0].body,
        )

    def test_delivered_email_is_not_sent_for_processing_order(self):
        result = send_order_delivered_notification(self.order.id)

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_recipient_does_not_send_email(self):
        result = send_customer_notification(
            subject="Test notification",
            template_name="notifications/emails/order_confirmation.txt",
            context={
                "order": self.order,
                "payment_prompt_sent": True,
            },
            recipient="",
        )

        self.assertFalse(result)
        self.assertEqual(len(mail.outbox), 0)

    @patch(
        "notifications.services.send_mail",
        side_effect=Exception("Email server unavailable"),
    )
    def test_email_failure_does_not_raise_exception(self, mock_send_mail):
        result = send_customer_notification(
            subject="Test notification",
            template_name="notifications/emails/order_confirmation.txt",
            context={
                "order": self.order,
                "payment_prompt_sent": True,
            },
            recipient="customer@example.com",
        )

        self.assertFalse(result)
        mock_send_mail.assert_called_once()
