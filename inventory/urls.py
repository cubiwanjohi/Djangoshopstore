
from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    path("receive/", views.receive_stock, name="receive_stock"),

    path("remove/", views.remove_stock, name="remove_stock"),

    path("movements/", views.movement_history, name="movement_history"),

    path(
        "products/<int:product_id>/history/",
        views.product_stock_history,
        name="product_stock_history",
    ),

    # Inventory reports
    path(
        "reports/",
        views.reports,
        name="reports",
    ),

    # Export inventory report as CSV
    path(
        "reports/export/",
        views.export_inventory_csv,
        name="export_inventory_csv",
    ),
]
