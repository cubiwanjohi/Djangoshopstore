from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from store.models import Order, OrderItem, Product, Payment
from orders.models import OrderStatusHistory
from .models import CustomerProfile

User = get_user_model()


class CustomerRegistrationTests(TestCase):

    def test_registration_page_loads(self):
        """The registration page should load successfully."""
        response = self.client.get(
            reverse("customers:register")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "customers/register.html",
        )

    def test_customer_can_register(self):
        """Registration should create a user and customer profile."""
        response = self.client.post(
            reverse("customers:register"),
            {
                "username": "testcustomer",
                "first_name": "Peter",
                "last_name": "Wanjohi",
                "email": "customer@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("customers:customer_login"),
        )

        user = User.objects.get(username="testcustomer")

        self.assertEqual(user.email, "customer@example.com")
        self.assertTrue(
            CustomerProfile.objects.filter(user=user).exists()
        )

    def test_duplicate_email_is_rejected(self):
        """Two accounts should not use the same email address."""
        User.objects.create_user(
            username="existingcustomer",
            email="customer@example.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            reverse("customers:register"),
            {
                "username": "newcustomer",
                "first_name": "New",
                "last_name": "Customer",
                "email": "CUSTOMER@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            User.objects.filter(username="newcustomer").exists()
        )


class CustomerAuthenticationTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="testcustomer",
            email="customer@example.com",
            password="StrongPass123!",
        )

        CustomerProfile.objects.create(user=self.user)

    def test_customer_can_login(self):
        """A customer should be able to log in."""
        response = self.client.post(
            reverse("customers:customer_login"),
            {
                "username": "testcustomer",
                "password": "StrongPass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("customers:customer_dashboard"),
        )

    def test_dashboard_requires_login(self):
        """Unauthenticated visitors should be redirected to login."""
        response = self.client.get(
            reverse("customers:customer_dashboard")
        )

        self.assertRedirects(
            response,
            f"{reverse('customers:customer_login')}?next="
            f"{reverse('customers:customer_dashboard')}",
        )

    def test_logged_in_customer_can_view_dashboard(self):
        """A logged-in customer should see their dashboard."""
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("customers:customer_dashboard")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "customers/dashboard.html",
        )
        self.assertEqual(
            response.context["profile"].user,
            self.user,
        )

    def test_dashboard_creates_missing_profile(self):
        """The dashboard should create a profile if one is missing."""
        CustomerProfile.objects.filter(user=self.user).delete()

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("customers:customer_dashboard")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            CustomerProfile.objects.filter(user=self.user).exists()
        )

    def test_customer_can_logout(self):
        """A customer should be logged out successfully."""
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("customers:customer_logout")
        )

        self.assertRedirects(
            response,
            reverse("customers:customer_login"),
        )

        dashboard_response = self.client.get(
            reverse("customers:customer_dashboard")
        )

        self.assertEqual(dashboard_response.status_code, 302)


class CustomerOrderTrackingTests(TestCase):

    def setUp(self):
        self.customer = User.objects.create_user(
            username="trackingcustomer",
            email="tracking@example.com",
            password="StrongPass123!",
        )

        self.other_customer = User.objects.create_user(
            username="anothercustomer",
            email="another@example.com",
            password="StrongPass123!",
        )

        self.product = Product.objects.create(
            name="Test Smartphone",
            description="A test product",
            price="1200.00",
            stock=10,
        )

        self.order = Order.objects.create(
            user=self.customer,
            customer_name="Tracking Customer",
            customer_email="tracking@example.com",
            shipping_address="Nairobi CBD",
            shipping_city="Nairobi",
            shipping_phone="0712345678",
            status="paid",
            delivery_status="shipped",
            tracking_number="SS-TRACK-001",
        )

        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=1,
            price="1200.00",
        )

        Payment.objects.create(
            order=self.order,
            method="mpesa",
            status="completed",
            amount="1200.00",
            mpesa_receipt_number="QWE123456",
        )

        OrderStatusHistory.objects.create(
            order=self.order,
            previous_status="processing",
            new_status="shipped",
            changed_by=self.customer,
            note="INTERNAL STAFF NOTE - test only",
        )

    def test_order_history_requires_login(self):
        """Visitors must log in before viewing their orders."""
        response = self.client.get(
            reverse("customers:customer_orders")
        )

        self.assertRedirects(
            response,
            f"{reverse('customers:customer_login')}?next="
            f"{reverse('customers:customer_orders')}",
        )

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

    def test_customer_can_view_own_order_history(self):
        """Customers should see their own orders."""
        self.client.force_login(self.customer)

        response = self.client.get(
            reverse("customers:customer_orders")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "customers/order_history.html",
        )
        self.assertContains(response, "SS-TRACK-001")
        self.assertContains(response, "Test Smartphone")

    def test_customer_cannot_view_another_customers_order(self):
        """Customers must not access orders belonging to others."""
        self.client.force_login(self.other_customer)

        response = self.client.get(
            reverse(
                "customers:customer_order_detail",
                args=[self.order.pk],
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_customer_order_history_excludes_other_customers_orders(self):
        """The order list must only contain the logged-in customer's orders."""
        other_order = Order.objects.create(
            user=self.other_customer,
            customer_name="Another Customer",
            customer_email="another@example.com",
        )

        self.client.force_login(self.customer)

        response = self.client.get(
            reverse("customers:customer_orders")
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Order #{self.order.pk}")
        self.assertNotContains(response, f"Order #{other_order.pk}")

    def test_customer_can_view_order_tracking_details(self):
        """Customers should see delivery, payment and tracking information."""
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

        self.assertContains(response, "SS-TRACK-001")
        self.assertContains(response, "Shipped")
        self.assertContains(response, "Your order has been dispatched.")
        self.assertContains(response, "QWE123456")
        self.assertContains(response, "Test Smartphone")

    def test_customer_does_not_see_internal_staff_notes(self):
        """Internal fulfilment notes must not appear in customer tracking."""
        self.client.force_login(self.customer)

        response = self.client.get(
            reverse(
                "customers:customer_order_detail",
                args=[self.order.pk],
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(
            response,
            "INTERNAL STAFF NOTE",
        )
