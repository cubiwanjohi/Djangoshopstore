
from django.contrib import admin

from .models import CustomerProfile, CustomerAddress


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number", "created_at")
    search_fields = ("user__username", "user__email", "phone_number")


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = (
        "recipient_name",
        "user",
        "label",
        "city",
        "county",
        "is_default",
    )

    list_filter = ("city", "county", "is_default")

    search_fields = (
        "recipient_name",
        "phone_number",
        "user__username",
        "city",
    )
