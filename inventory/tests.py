
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from .services import adjust_stock, InsufficientStockError
from store.models import Product, Order
from .models import StockMovement


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
