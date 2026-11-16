
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .services import adjust_stock, InsufficientStockError
from store.models import Product, Order
from .models import StockMovement, InventorySettings


User = get_user_model()


class StockMovementModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="inventory_admin",
            password="TestPassword123!",
        )

        self.product = Product.objects.create(
            name="Test Product",
            description="Inventory testing product",
            price=Decimal("1500.00"),
            stock=20,
        )

        self.order = Order.objects.create(
            user=self.user,
            customer_name="Test Customer",
            customer_email="customer@example.com",
        )

    def test_create_stock_received_movement(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.IN,
            quantity=10,
            note="New stock received",
            created_by=self.user,
        )

        self.assertEqual(movement.product, self.product)
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.movement_type, "IN")
        self.assertEqual(movement.created_by, self.user)

    def test_create_reserved_stock_movement(self):
        movement = StockMovement.objects.create(
            product=self.product,
            order=self.order,
            movement_type=StockMovement.MovementType.RESERVED,
            quantity=2,
        )

        self.assertEqual(movement.order, self.order)
        self.assertEqual(movement.movement_type, "RESERVED")

    def test_create_returned_stock_movement(self):
        movement = StockMovement.objects.create(
            product=self.product,
            order=self.order,
            movement_type=StockMovement.MovementType.RETURNED,
            quantity=2,
            note="M-Pesa payment failed",
        )

        self.assertEqual(movement.movement_type, "RETURNED")
        self.assertEqual(movement.quantity, 2)

    def test_quantity_must_be_at_least_one(self):
        movement = StockMovement(
            product=self.product,
            movement_type=StockMovement.MovementType.IN,
            quantity=0,
        )

        with self.assertRaises(ValidationError):
            movement.full_clean()

    def test_stock_movement_does_not_change_product_stock(self):
        original_stock = self.product.stock

        StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.IN,
            quantity=5,
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, original_stock)

    def test_movement_string_representation(self):
        movement = StockMovement.objects.create(
            product=self.product,
            movement_type=StockMovement.MovementType.IN,
            quantity=5,
        )

        self.assertEqual(
            str(movement),
            "Stock Received - Test Product (5)",
        )

class InventoryStockServiceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="stock_manager",
            password="TestPassword123!",
        )

        self.product = Product.objects.create(
            name="Service Test Product",
            description="Testing stock adjustments",
            price=Decimal("500.00"),
            stock=20,
        )

    def test_receive_stock_increases_product_stock(self):
        movement = adjust_stock(
            product_id=self.product.pk,
            movement_type=StockMovement.MovementType.IN,
            quantity=10,
            note="Supplier delivery",
            created_by=self.user,
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, 30)
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.movement_type, "IN")
        self.assertEqual(movement.created_by, self.user)

    def test_remove_stock_decreases_product_stock(self):
        movement = adjust_stock(
            product_id=self.product.pk,
            movement_type=StockMovement.MovementType.OUT,
            quantity=5,
            note="Damaged stock",
            created_by=self.user,
        )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, 15)
        self.assertEqual(movement.quantity, 5)
        self.assertEqual(movement.movement_type, "OUT")

    def test_cannot_remove_more_stock_than_available(self):
        with self.assertRaises(InsufficientStockError):
            adjust_stock(
                product_id=self.product.pk,
                movement_type=StockMovement.MovementType.OUT,
                quantity=25,
            )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, 20)
        self.assertEqual(
            StockMovement.objects.filter(
                product=self.product,
            ).count(),
            0,
        )

    def test_zero_quantity_is_rejected(self):
        with self.assertRaises(ValidationError):
            adjust_stock(
                product_id=self.product.pk,
                movement_type=StockMovement.MovementType.IN,
                quantity=0,
            )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, 20)

    def test_reserved_movement_cannot_use_manual_adjustment(self):
        with self.assertRaises(ValidationError):
            adjust_stock(
                product_id=self.product.pk,
                movement_type=StockMovement.MovementType.RESERVED,
                quantity=2,
            )

        self.product.refresh_from_db()

        self.assertEqual(self.product.stock, 20)

class InventoryStockAdjustmentViewTests(TestCase):

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="inventory_staff",
            password="TestPassword123!",
            is_staff=True,
        )

        self.customer = User.objects.create_user(
            username="normal_customer",
            password="TestPassword123!",
            is_staff=False,
        )

        self.product = Product.objects.create(
            name="Dashboard Test Product",
            description="Testing inventory dashboard operations",
            price=Decimal("1200.00"),
            stock=20,
        )

        self.receive_url = reverse("inventory:receive_stock")
        self.remove_url = reverse("inventory:remove_stock")
        self.dashboard_url = reverse("inventory:dashboard")

    def test_staff_can_access_receive_stock_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.receive_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Receive Stock")

    def test_staff_can_access_remove_stock_page(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.remove_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Remove Stock")

    def test_customer_cannot_access_receive_stock_page(self):
        self.client.force_login(self.customer)

        response = self.client.get(self.receive_url)

        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_access_remove_stock_page(self):
        self.client.force_login(self.customer)

        response = self.client.get(self.remove_url)

        self.assertEqual(response.status_code, 403)

    def test_staff_can_receive_stock(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            self.receive_url,
            {
                "product": self.product.pk,
                "quantity": 10,
                "note": "Supplier delivery",
            },
        )

        self.product.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.dashboard_url)
        self.assertEqual(self.product.stock, 30)

        movement = StockMovement.objects.get(
            product=self.product,
            movement_type=StockMovement.MovementType.IN,
        )

        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.created_by, self.staff_user)
        self.assertEqual(movement.note, "Supplier delivery")

    def test_staff_can_remove_stock(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            self.remove_url,
            {
                "product": self.product.pk,
                "quantity": 5,
                "note": "Damaged products",
            },
        )

        self.product.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, self.dashboard_url)
        self.assertEqual(self.product.stock, 15)

        movement = StockMovement.objects.get(
            product=self.product,
            movement_type=StockMovement.MovementType.OUT,
        )

        self.assertEqual(movement.quantity, 5)
        self.assertEqual(movement.created_by, self.staff_user)
        self.assertEqual(movement.note, "Damaged products")

    def test_removing_more_than_available_stock_is_rejected(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            self.remove_url,
            {
                "product": self.product.pk,
                "quantity": 25,
                "note": "Test insufficient stock",
            },
        )

        self.product.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.product.stock, 20)
        self.assertEqual(StockMovement.objects.count(), 0)
        self.assertTrue(response.context["form"].non_field_errors())


class InventorySettingsViewTests(TestCase):

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="settings_staff",
            password="TestPassword123!",
            is_staff=True,
        )

        self.customer = User.objects.create_user(
            username="settings_customer",
            password="TestPassword123!",
            is_staff=False,
        )

        self.product = Product.objects.create(
            name="Settings Test Product",
            description="Testing inventory settings",
            price=Decimal("1000.00"),
            stock=20,
        )

        self.dashboard_url = reverse("inventory:dashboard")

    def test_default_low_stock_threshold_is_five(self):
        settings = InventorySettings.load()

        self.assertEqual(settings.low_stock_threshold, 5)
        self.assertEqual(InventorySettings.objects.count(), 1)

    def test_staff_can_access_inventory_dashboard(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inventory Settings")
        self.assertEqual(
            response.context["low_stock_threshold"],
            5,
        )

    def test_customer_cannot_access_inventory_dashboard(self):
        self.client.force_login(self.customer)

        response = self.client.get(self.dashboard_url)

        self.assertEqual(response.status_code, 403)

    def test_staff_can_update_low_stock_threshold(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            self.dashboard_url,
            {
                "low_stock_threshold": 10,
            },
        )

        self.assertRedirects(response, self.dashboard_url)

        settings = InventorySettings.objects.get(pk=1)
        self.assertEqual(settings.low_stock_threshold, 10)

        # Changing the threshold must not change product stock.
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 20)

    def test_negative_low_stock_threshold_is_rejected(self):
        self.client.force_login(self.staff_user)

        response = self.client.post(
            self.dashboard_url,
            {
                "low_stock_threshold": -1,
            },
        )

        self.assertEqual(response.status_code, 200)

        settings = InventorySettings.objects.get(pk=1)
        self.assertEqual(settings.low_stock_threshold, 5)

        self.assertTrue(
            response.context["threshold_form"].errors
        )


class InventoryReportsTests(TestCase):

    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="reports_staff",
            password="TestPassword123!",
            is_staff=True,
        )

        self.customer = User.objects.create_user(
            username="reports_customer",
            password="TestPassword123!",
            is_staff=False,
        )

        self.product_one = Product.objects.create(
            name="Laptop",
            description="Business laptop",
            price=Decimal("1500.00"),
            stock=8,
        )

        self.product_two = Product.objects.create(
            name="Keyboard",
            description="Wireless keyboard",
            price=Decimal("250.00"),
            stock=3,
        )

        self.reports_url = reverse("inventory:reports")

        self.csv_url = reverse(
            "inventory:export_inventory_csv"
        )

        InventorySettings.load()

        # Set the low-stock threshold to 5.
        settings = InventorySettings.objects.get(pk=1)
        settings.low_stock_threshold = 5
        settings.save()

        # Create stock movement records.
        StockMovement.objects.create(
            product=self.product_one,
            movement_type=StockMovement.MovementType.IN,
            quantity=10,
            note="Supplier delivery",
            created_by=self.staff_user,
        )

        StockMovement.objects.create(
            product=self.product_one,
            movement_type=StockMovement.MovementType.OUT,
            quantity=4,
            note="Damaged stock",
            created_by=self.staff_user,
        )

        StockMovement.objects.create(
            product=self.product_one,
            movement_type=StockMovement.MovementType.RESERVED,
            quantity=2,
        )

        StockMovement.objects.create(
            product=self.product_two,
            movement_type=StockMovement.MovementType.RETURNED,
            quantity=1,
        )

    def test_staff_can_access_inventory_reports(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.reports_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "inventory/reports.html",
        )

    def test_customer_cannot_access_inventory_reports(self):
        self.client.force_login(self.customer)

        response = self.client.get(self.reports_url)

        self.assertEqual(response.status_code, 403)

    def test_inventory_report_calculations_are_correct(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.reports_url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response.context["total_products"],
            2,
        )

        self.assertEqual(
            response.context["total_stock"],
            11,
        )

        self.assertEqual(
            response.context["inventory_value"],
            Decimal("12750.00"),
        )

        self.assertEqual(
            response.context["total_received"],
            10,
        )

        self.assertEqual(
            response.context["total_removed"],
            4,
        )

        self.assertEqual(
            response.context["total_reserved"],
            2,
        )

        self.assertEqual(
            response.context["total_returned"],
            1,
        )

    def test_low_stock_products_are_reported_correctly(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.reports_url)

        self.assertEqual(
            response.context["low_stock_count"],
            1,
        )

        low_stock_products = list(
            response.context["low_stock_products"]
        )

        self.assertEqual(
            low_stock_products[0],
            self.product_two,
        )

    def test_staff_can_export_inventory_csv(self):
        self.client.force_login(self.staff_user)

        response = self.client.get(self.csv_url)

        self.assertEqual(response.status_code, 200)

        self.assertEqual(
            response["Content-Type"],
            "text/csv; charset=utf-8",
        )

        self.assertIn(
            "shopstore_inventory_report.csv",
            response["Content-Disposition"],
        )

        csv_content = response.content.decode("utf-8")

        self.assertIn("Laptop", csv_content)
        self.assertIn("Keyboard", csv_content)
        self.assertIn("1500.00", csv_content)
        self.assertIn("250.00", csv_content)
        self.assertIn("LOW STOCK", csv_content)
        self.assertIn("NORMAL", csv_content)

    def test_customer_cannot_export_inventory_csv(self):
        self.client.force_login(self.customer)

        response = self.client.get(self.csv_url)

        self.assertEqual(response.status_code, 403)
