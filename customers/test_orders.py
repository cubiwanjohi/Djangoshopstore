
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from store.models import Order, OrderItem, Payment, Product

User = get_user_model()


class CustomerOrderHistoryTests(TestCase):
    """Test customer order history and order ownership."""

    def setUp(self):
        self.customer = User.objects.create_user(
            username="customer1",
            email="customer1@example.com",
            password="StrongPass123!",
        )

        self.other_customer = User.objects.create_user(
            username="customer2",
            email="customer2@example.com",
            password="StrongPass123!",
        )

        self.product = Product.objects.create(
            name="Headphones",
            description="Wireless headphones",
            price=Decimal("2000.00"),
            stock=10,
        )

        self.order = Order.objects.create(
            user=self.customer,
            customer_name="Customer One",
            customer_email="customer1@example.com",
            shipping_address="Kerugoya Road",
            shipping_city="Kerugoya",
            shipping_phone="0712345678",
        )

        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal("2000.00"),
        )

        self.payment = Payment.objects.create(
            order=self.order,
            amount=Decimal("4000.00"),
            mpesa_phone="254712345678",
            transaction_id="TEST-MPESA-123",
            status="completed",
        )

        self.other_order = Order.objects.create(
            user=self.other_customer,
            customer_name="Customer Two",
            customer_email="customer2@example.com",
        )

    def test_order_history_requires_login(self):
        """Visitors must log in before viewing order history."""

        response = self.client.get(
            reverse("customers:customer_orders")
        )

        self.assertRedirects(
            response,
            f"{reverse('customers:customer_login')}?next="
            f"{reverse('customers:customer_orders')}",
        )

    def test_customer_can_view_own_order_history(self):
        """A customer should see their own orders."""

        self.client.force_login(self.customer)

        response = self.client.get(
            reverse("customers:customer_orders")
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "customers/order_history.html",
        )

        orders = response.context["orders"]

        self.assertIn(self.order, orders)
        self.assertNotIn(self.other_order, orders)

    def test_customer_cannot_see_another_customers_orders(self):
        """Order history must exclude other customers' orders."""

        self.client.force_login(self.customer)

        response = self.client.get(
            reverse("customers:customer_orders")
        )

        order_ids = [
            order.pk
            for order in response.context["orders"]
        ]

        self.assertIn(self.order.pk, order_ids)
        self.assertNotIn(self.other_order.pk, order_ids)

    def test_order_detail_requires_login(self):
        """Visitors must log in before viewing order details."""

        response = self.client.get(
            reverse(
                "customers:customer_order_detail",
                args=[self.order.pk],
            )
        )

        self.assertRedirects(
            response,
            f"{reverse('customers:customer_login')}?next="
            f"{reverse('customers:customer_order_detail', args=[self.order.pk])}",
        )

    def test_customer_can_view_own_order_details(self):
        """A customer should see their order and payment information."""

        self.client.force_login(self.customer)

        response = self.client.get(
            reverse(
                "customers:customer_order_detail",
                args=[self.order.pk],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "customers/order_detail.html",
        )

        self.assertEqual(
            response.context["order"],
            self.order,
        )

        self.assertContains(response, "Headphones")
        self.assertContains(response, "4000.00")
        self.assertContains(response, "TEST-MPESA-123")
        self.assertContains(response, "254712345678")

    def test_customer_cannot_view_another_customers_order(self):
        """A customer must receive 404 for another customer's order."""

        self.client.force_login(self.customer)

        response = self.client.get(
            reverse(
                "customers:customer_order_detail",
                args=[self.other_order.pk],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_order_total_is_calculated_correctly(self):
        """Order details should calculate the correct total."""

        self.assertEqual(
            self.order.total(),
            Decimal("4000.00"),
        )

    def test_customer_with_no_orders_sees_empty_history(self):
        """Customers without orders should see the empty state."""

        new_customer = User.objects.create_user(
            username="newcustomer",
            email="newcustomer@example.com",
            password="StrongPass123!",
        )

        self.client.force_login(new_customer)

        response = self.client.get(
            reverse("customers:customer_orders")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "You haven't placed any orders yet.",
        )
        self.assertEqual(len(response.context["orders"]), 0)
