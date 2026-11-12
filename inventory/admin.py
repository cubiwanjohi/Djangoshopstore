
from django.contrib import admin

from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "movement_type",
        "quantity",
        "order",
        "created_by",
        "created_at",
    )

    list_filter = ("movement_type", "created_at")

    search_fields = (
        "product__name",
        "order__id",
        "note",
        "created_by__username",
    )

    readonly_fields = (
        "product",
        "order",
        "movement_type",
        "quantity",
        "note",
        "created_by",
        "created_at",
    )

    date_hierarchy = "created_at"

    list_select_related = ("product", "order", "created_by")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
