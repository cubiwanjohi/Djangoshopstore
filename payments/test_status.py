from django.core import signing
from django.test import TestCase
from django.urls import reverse

from store.models import Order, Payment


class PaymentStatusTests(TestCase):

    def setUp(self):
        self.order = Order.objects.create(
            customer_name="Test Customer",
            customer_email="test@example.com",
            shipping_address="Test Address",
            shipping_city="Nairobi",
            shipping_phone="0712345678",
        )

        self.payment = Payment.objects.create(
            order=self.order,
            method="mpesa",
            amount="100.00",
            status="pending",
        )

        self.token = signing.dumps(
            {"order_id": self.order.pk},
            salt="payments.order-status",
        )

        self.url = reverse(
            "payment_status",
            args=[self.token],
        )

    def test_pending_payment_status(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "pending")
        self.assertEqual(
            response["Cache-Control"],
            "no-store",
        )

    def test_completed_payment_status(self):
        self.payment.status = "completed"
        self.payment.save(update_fields=["status"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "completed")

    def test_failed_payment_status(self):
        self.payment.status = "failed"
        self.payment.save(update_fields=["status"])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")

    def test_invalid_token_is_rejected(self):
        response = self.client.get(
            reverse(
                "payment_status",
                args=["invalid-token"],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_token_signed_with_different_secret_is_rejected(self):
        expired_token = signing.dumps(
            {"order_id": self.order.pk},
            salt="payments.order-status",
        )

        with self.settings(SECRET_KEY="a-different-secret-key"):
            response = self.client.get(
                reverse(
                    "payment_status",
                    args=[expired_token],
                )
            )

        self.assertEqual(response.status_code, 404)

    def test_unknown_order_is_rejected(self):
        token = signing.dumps(
            {"order_id": 999999},
            salt="payments.order-status",
        )

        response = self.client.get(
            reverse("payment_status", args=[token])
        )

        self.assertEqual(response.status_code, 404)

    def test_endpoint_rejects_post_requests(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 405)

    def test_signed_non_dictionary_payload_is_rejected(self):
        token = signing.dumps(
            ["not", "a", "dictionary"],
            salt="payments.order-status",
        )

        response = self.client.get(
            reverse("payment_status", args=[token])
        )

        self.assertEqual(response.status_code, 404)