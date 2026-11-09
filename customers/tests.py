
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

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
