
from django.conf import settings
from django.db import models


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_profile",
    )

    phone_number = models.CharField(
        max_length=20,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.username}"


class CustomerAddress(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_addresses",
    )

    label = models.CharField(
        max_length=50,
        default="Home",
    )

    recipient_name = models.CharField(max_length=200)

    phone_number = models.CharField(max_length=20)

    address_line = models.CharField(max_length=255)

    city = models.CharField(max_length=100)

    county = models.CharField(max_length=100, blank=True)

    is_default = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.label} - {self.city} ({self.user.username})"
