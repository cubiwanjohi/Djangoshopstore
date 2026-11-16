
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from store.models import Product, Order


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        IN = "IN", "Stock Received"
        OUT = "OUT", "Stock Removed"
        RESERVED = "RESERVED", "Stock Reserved"
        RETURNED = "RETURNED", "Stock Returned"

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    order = models.ForeignKey(
        Order,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )

    note = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "created_at"]),
            models.Index(fields=["movement_type", "created_at"]),
        ]

    def __str__(self):
        return (
            f"{self.get_movement_type_display()} - "
            f"{self.product.name} ({self.quantity})"
        )

class InventorySettings(models.Model):
    """
    Store inventory configuration.

    The application uses one settings record with primary key 1.
    """

    low_stock_threshold = models.PositiveIntegerField(
        default=5,
        validators=[MinValueValidator(0)],
        help_text="Products at or below this quantity are considered low stock.",
    )

    class Meta:
        verbose_name = "Inventory Settings"
        verbose_name_plural = "Inventory Settings"

    def __str__(self):
        return f"Low stock threshold: {self.low_stock_threshold}"

    @classmethod
    def load(cls):
        settings, created = cls.objects.get_or_create(
            pk=1,
            defaults={"low_stock_threshold": 5},
        )
        return settings

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
