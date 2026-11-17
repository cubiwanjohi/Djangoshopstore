from django.conf import settings
from django.db import models

from store.models import Order

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="status_history",
    )

    previous_status = models.CharField(max_length=20)

    new_status = models.CharField(
        max_length=20,
        choices=Order.DELIVERY_STATUS_CHOICES,
    )

    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_changes",
    )

    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order Status History"
        verbose_name_plural = "Order Status History"

    def __str__(self):
        return (
            f"Order #{self.order_id}: "
            f"{self.previous_status} → {self.new_status}"
        )
