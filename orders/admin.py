
from django.contrib import admin

from .models import OrderStatusHistory


@admin.register(OrderStatusHistory)
class OrderStatusHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "order",
        "previous_status",
        "new_status",
        "changed_by",
        "created_at",
    )

    list_filter = (
        "previous_status",
        "new_status",
        "created_at",
    )

    search_fields = (
        "order__id",
        "changed_by__username",
        "note",
    )

    readonly_fields = (
        "order",
        "previous_status",
        "new_status",
        "changed_by",
        "note",
        "created_at",
    )

    ordering = ("-created_at",)
