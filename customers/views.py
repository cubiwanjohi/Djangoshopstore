
from django.contrib import messages
from django.db import transaction
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import CustomerRegistrationForm
from .models import CustomerProfile
from store.models import Order


def register(request):
    # Redirect authenticated customers to their dashboard.
    if request.user.is_authenticated:
        return redirect("customers:customer_dashboard")

    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)

        if form.is_valid():
            # Create the user and profile together.
            with transaction.atomic():
                user = form.save()
                CustomerProfile.objects.create(user=user)

            messages.success(
                request,
                "Your account has been created successfully. Please log in."
            )

            return redirect("customers:customer_login")

    else:
        form = CustomerRegistrationForm()

    return render(
        request,
        "customers/register.html",
        {"form": form},
    )


@login_required
def customer_dashboard(request):
    profile, created = CustomerProfile.objects.get_or_create(
        user=request.user
    )

    addresses = request.user.customer_addresses.all()

    return render(
        request,
        "customers/dashboard.html",
        {
            "profile": profile,
            "addresses": addresses,
        },
    )


@login_required
def customer_order_history(request):
    """Display orders belonging to the logged-in customer."""

    orders = (
        Order.objects
        .filter(user=request.user)
        .select_related("payment")
        .prefetch_related("items__product")
        .order_by("-created_at")
    )

    return render(
        request,
        "customers/order_history.html",
        {"orders": orders},
    )


@login_required
def customer_order_detail(request, pk):
    """Display an order only if it belongs to the logged-in customer."""

    order = get_object_or_404(
        Order.objects
        .filter(user=request.user)
        .select_related("payment")
        .prefetch_related("items__product"),
        pk=pk,
    )

    return render(
        request,
        "customers/order_detail.html",
        {"order": order},
    )
