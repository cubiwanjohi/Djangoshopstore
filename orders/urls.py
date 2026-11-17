
from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path(
        "management/",
        views.fulfilment_dashboard,
        name="fulfilment_dashboard",
    ),
    path(
        "management/<int:pk>/",
        views.fulfilment_order_detail,
        name="fulfilment_order_detail",
    ),
    path(
        "management/<int:pk>/update/",
        views.update_fulfilment_status,
        name="update_fulfilment_status",
    ),
]
