from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from store.models import Order, OrderItem, Product

from .models import OrderStatusHistory
from unittest.mock import patch

User = get_user_model()


class OrderFulfilmentTests(TestCase):

    def setUp(self):
        self.staff = User.objects.create_user(
            username="fulfilmentstaff",
            email="staff@example.com",
            password="StrongPass123!",
            is_staff=True,
        )

        self.customer = User.objects.create_user(
            username="testcustomer",
            email="customer@example.com",
            password="StrongPass123!",
        )

        self.product = Product.objects.create(
            name="Test Product",
            description="Product for fulfilment tests",
            price=Decimal("100.00"),
            stock=10,
        )

        self.order = Order.objects.create(
            user=self.customer,
            status="paid",
            customer_name="Test Customer",
            customer_email="customer@example.com",
            shipping_address="Test Street",
            shipping_city="Nairobi",
            shipping_phone="254712345678",
        )

        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal("100.00"),
        )

        self.dashboard_url = reverse(
            "orders:fulfilment_dashboard"
        )

        self.detail_url = reverse(
            "orders:fulfilment_order_detail",
            args=[self.order.pk],
        )

        self.update_url = reverse(
            "orders:update_fulfilment_status",
            args=[self.order.pk],
        )

    def test_staff_can_view_fulfilment_dashboard(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "orders/fulfilment_dashboard.html",
        )
        self.assertContains(response, "Test Customer")

    def test_staff_can_view_order_details(self):
        self.client.force_login(self.staff)

        response = self.client.get(self.detail_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "orders/fulfilment_detail.html",
        )
        self.assertContains(response, "Test Product")

    def test_customer_cannot_access_fulfilment_dashboard(self):
        self.client.force_login(self.customer)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 302)

    def test_customer_cannot_update_order_fulfilment(self):
        self.client.force_login(self.customer)

        response = self.client.post(
            self.update_url,
            {
                "delivery_status": "shipped",
                "tracking_number": "TRACK123",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.delivery_status,
            "processing",
        )
        self.assertFalse(
            OrderStatusHistory.objects.filter(
                order=self.order
            ).exists()
        )

    def test_unpaid_order_cannot_be_dispatched(self):
        self.order.status = "pending"
        self.order.save(update_fields=["status"])

        self.client.force_login(self.staff)

        response = self.client.post(
            self.update_url,
            {
                "delivery_status": "shipped",
                "tracking_number": "TRACK123",
            },
        )

        self.assertRedirects(response, self.detail_url)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.delivery_status,
            "processing",
        )
        self.assertFalse(
            OrderStatusHistory.objects.filter(
                order=self.order
            ).exists()
        )

    def test_paid_order_can_be_dispatched(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            self.update_url,
            {
                "delivery_status": "shipped",
                "tracking_number": "TRACK123",
                "note": "Package handed to courier",
            },
        )

        self.assertRedirects(response, self.detail_url)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.delivery_status,
            "shipped",
        )
        self.assertEqual(
            self.order.tracking_number,
            "TRACK123",
        )
        self.assertIsNotNone(self.order.shipped_at)
        self.assertIsNone(self.order.delivered_at)

        history = OrderStatusHistory.objects.get(
            order=self.order
        )

        self.assertEqual(
            history.previous_status,
            "processing",
        )
        self.assertEqual(history.new_status, "shipped")
        self.assertEqual(history.changed_by, self.staff)
        self.assertEqual(
            history.note,
            "Package handed to courier",
        )

    def test_shipped_order_can_be_marked_delivered(self):
        self.order.delivery_status = "shipped"
        self.order.tracking_number = "TRACK123"
        self.order.save(
            update_fields=[
                "delivery_status",
                "tracking_number",
            ]
        )

        self.client.force_login(self.staff)

        response = self.client.post(
            self.update_url,
            {
                "delivery_status": "delivered",
                "note": "Customer received the package",
            },
        )

        self.assertRedirects(response, self.detail_url)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.delivery_status,
            "delivered",
        )
        self.assertIsNotNone(self.order.delivered_at)

        history = OrderStatusHistory.objects.get(
            order=self.order
        )

        self.assertEqual(history.new_status, "delivered")
        self.assertEqual(
            history.previous_status,
            "shipped",
        )
        self.assertEqual(history.changed_by, self.staff)

    def test_invalid_status_transition_is_rejected(self):
        self.client.force_login(self.staff)

        response = self.client.post(
            self.update_url,
            {
                "delivery_status": "delivered",
            },
        )

        self.assertRedirects(response, self.detail_url)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.delivery_status,
            "processing",
        )
        self.assertFalse(
            OrderStatusHistory.objects.filter(
                order=self.order
            ).exists()
        )
    @patch("orders.views.send_order_shipped_notification")
    def test_shipping_notification_is_triggered(self, mock_notification):
        self.client.force_login(self.staff)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.update_url,
                {
                    "delivery_status": "shipped",
                    "tracking_number": "TRACK123",
                    "note": "Package dispatched",
                },
            )

        self.assertRedirects(response, self.detail_url)
        mock_notification.assert_called_once_with(self.order.pk)

    @patch("orders.views.send_order_delivered_notification")
    def test_delivery_notification_is_triggered(self, mock_notification):
        self.order.delivery_status = "shipped"
        self.order.save(update_fields=["delivery_status"])

        self.client.force_login(self.staff)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.update_url,
                {
                    "delivery_status": "delivered",
                    "note": "Package delivered",
                },
            )

        self.assertRedirects(response, self.detail_url)
        mock_notification.assert_called_once_with(self.order.pk)