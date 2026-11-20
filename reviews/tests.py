
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from store.models import Order, OrderItem, Product

from .forms import ReviewForm
from .models import Review


User = get_user_model()


class ReviewFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="customer1",
            email="customer1@example.com",
            password="TestPassword123!",
        )

        self.other_user = User.objects.create_user(
            username="customer2",
            email="customer2@example.com",
            password="TestPassword123!",
        )

        self.product = Product.objects.create(
            name="Samsung Laptop",
            description="A reliable laptop",
            price=Decimal("75000.00"),
            stock=10,
        )

        self.paid_order = Order.objects.create(
            user=self.user,
            status="paid",
            customer_name="Customer One",
            customer_email="customer1@example.com",
        )

        self.order_item = OrderItem.objects.create(
            order=self.paid_order,
            product=self.product,
            quantity=1,
            price=self.product.price,
        )

        self.create_url = reverse(
            "reviews:create_review",
            args=[self.product.pk],
        )

    def review_data(self, rating=5):
        return {
            "rating": rating,
            "title": "Excellent product",
            "comment": "I am very happy with this purchase.",
        }

    def create_review_for_user(self, user, rating=5):
        return Review.objects.create(
            product=self.product,
            user=user,
            rating=rating,
            title="Good product",
            comment="Works as expected.",
        )

    def test_review_requires_login(self):
        response = self.client.get(self.create_url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url.lower())

    def test_customer_can_review_paid_purchase(self):
        self.client.force_login(self.user)

        response = self.client.post(
            self.create_url,
            self.review_data(),
        )

        self.assertRedirects(
            response,
            reverse("product_detail", args=[self.product.pk]),
        )

        review = Review.objects.get(
            product=self.product,
            user=self.user,
        )

        self.assertEqual(review.rating, 5)
        self.assertEqual(review.title, "Excellent product")

    def test_customer_cannot_review_without_purchase(self):
        self.paid_order.delete()

        self.client.force_login(self.user)

        response = self.client.post(
            self.create_url,
            self.review_data(),
        )

        self.assertRedirects(
            response,
            reverse("product_detail", args=[self.product.pk]),
        )

        self.assertFalse(
            Review.objects.filter(
                product=self.product,
                user=self.user,
            ).exists()
        )

    def test_customer_cannot_review_pending_order(self):
        self.paid_order.status = "pending"
        self.paid_order.save()

        self.client.force_login(self.user)

        self.client.post(
            self.create_url,
            self.review_data(),
        )

        self.assertFalse(
            Review.objects.filter(
                product=self.product,
                user=self.user,
            ).exists()
        )

    def test_customer_cannot_review_another_users_purchase(self):
        self.client.force_login(self.other_user)

        self.client.post(
            self.create_url,
            self.review_data(),
        )

        self.assertFalse(
            Review.objects.filter(
                product=self.product,
                user=self.other_user,
            ).exists()
        )

    def test_customer_cannot_submit_duplicate_review(self):
        existing_review = self.create_review_for_user(self.user)

        self.client.force_login(self.user)

        response = self.client.post(
            self.create_url,
            self.review_data(rating=3),
        )

        self.assertRedirects(
            response,
            reverse(
                "reviews:edit_review",
                args=[existing_review.pk],
            ),
        )

        self.assertEqual(
            Review.objects.filter(
                product=self.product,
                user=self.user,
            ).count(),
            1,
        )

    def test_rating_must_be_between_one_and_five(self):
        for rating in (0, 6):
            form = ReviewForm(data=self.review_data(rating=rating))

            self.assertFalse(form.is_valid())
            self.assertIn("rating", form.errors)

    def test_review_form_accepts_valid_rating(self):
        form = ReviewForm(data=self.review_data(rating=4))

        self.assertTrue(form.is_valid(), form.errors)

    def test_customer_can_edit_own_review(self):
        review = self.create_review_for_user(self.user)

        self.client.force_login(self.user)

        response = self.client.post(
            reverse("reviews:edit_review", args=[review.pk]),
            self.review_data(rating=3),
        )

        self.assertRedirects(
            response,
            reverse("product_detail", args=[self.product.pk]),
        )

        review.refresh_from_db()
        self.assertEqual(review.rating, 3)
        self.assertEqual(review.title, "Excellent product")

    def test_customer_cannot_edit_another_users_review(self):
        review = self.create_review_for_user(self.user)

        self.client.force_login(self.other_user)

        response = self.client.get(
            reverse("reviews:edit_review", args=[review.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_customer_can_delete_own_review(self):
        review = self.create_review_for_user(self.user)

        self.client.force_login(self.user)

        response = self.client.post(
            reverse("reviews:delete_review", args=[review.pk])
        )

        self.assertRedirects(
            response,
            reverse("product_detail", args=[self.product.pk]),
        )

        self.assertFalse(
            Review.objects.filter(pk=review.pk).exists()
        )

    def test_customer_cannot_delete_another_users_review(self):
        review = self.create_review_for_user(self.user)

        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse("reviews:delete_review", args=[review.pk])
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            Review.objects.filter(pk=review.pk).exists()
        )

    def test_delete_review_requires_post(self):
        review = self.create_review_for_user(self.user)

        self.client.force_login(self.user)

        response = self.client.get(
            reverse("reviews:delete_review", args=[review.pk])
        )

        self.assertEqual(response.status_code, 405)
        self.assertTrue(
            Review.objects.filter(pk=review.pk).exists()
        )

    def test_product_page_displays_reviews_and_average_rating(self):
        self.create_review_for_user(self.user, rating=5)

        second_order = Order.objects.create(
            user=self.other_user,
            status="paid",
            customer_name="Customer Two",
            customer_email="customer2@example.com",
        )

        OrderItem.objects.create(
            order=second_order,
            product=self.product,
            quantity=1,
            price=self.product.price,
        )

        Review.objects.create(
            product=self.product,
            user=self.other_user,
            rating=3,
            title="Good but could improve",
            comment="The product is useful.",
        )

        response = self.client.get(
            reverse("product_detail", args=[self.product.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["review_count"], 2)
        self.assertEqual(response.context["average_rating"], 4.0)

        self.assertContains(response, "Good product")
        self.assertContains(response, "Good but could improve")

    def test_product_page_displays_no_reviews_message(self):
        response = self.client.get(
            reverse("product_detail", args=[self.product.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["review_count"], 0)
        self.assertIsNone(response.context["average_rating"])
        self.assertContains(response, "No customer reviews yet")
