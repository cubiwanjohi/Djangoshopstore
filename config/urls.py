
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path("admin/", admin.site.urls),

    # Customer functionality
    path("customers/", include("customers.urls")),

    # Inventory management
    path("inventory/", include("inventory.urls")),

    # Store functionality
    path("", include("store.urls")),

    # M-Pesa payments
    path("", include("payments.urls")),

    # Order fulfilment management
    path("orders/", include("orders.urls")),

    # Product reviews
    path("reviews/", include("reviews.urls")),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )
