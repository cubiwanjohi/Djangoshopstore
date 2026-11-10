
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views

from . import views

app_name = "customers"

urlpatterns = [
    # Customer registration
    path(
        "register/",
        views.register,
        name="register",
    ),

    # Customer login
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="customers/login.html",
            redirect_authenticated_user=True,
            next_page=reverse_lazy(
                "customers:customer_dashboard"
            ),
        ),
        name="customer_login",
    ),

    # Customer logout
    path(
        "logout/",
        auth_views.LogoutView.as_view(
            next_page=reverse_lazy(
                "customers:customer_login"
            ),
        ),
        name="customer_logout",
    ),

    # Customer dashboard
    path(
        "dashboard/",
        views.customer_dashboard,
        name="customer_dashboard",
    ),

    # Customer order history
    path(
        "orders/",
        views.customer_order_history,
        name="customer_orders",
    ),

    # Individual order details
    path(
        "orders/<int:pk>/",
        views.customer_order_detail,
        name="customer_order_detail",
    ),
]
