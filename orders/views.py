
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from notifications.services import (
    send_order_delivered_notification,
    send_order_shipped_notification,
)
from store.models import Order

from .models import OrderStatusHistory


@staff_member_required
def fulfilment_dashboard(request):
    orders = (
        Order.objects
        .select_related("user")
        .prefetch_related("items")
        .order_by("-created_at")
    )

    delivery_status = request.GET.get("delivery_status", "")
    order_status = request.GET.get("order_status", "")
    search = request.GET.get("search", "").strip()

    if delivery_status in dict(Order.DELIVERY_STATUS_CHOICES):
        orders = orders.filter(delivery_status=delivery_status)

    if order_status in dict(Order.STATUS_CHOICES):
        orders = orders.filter(status=order_status)

    if search:
        if search.isdigit():
            orders = orders.filter(pk=search)
        else:
            orders = orders.filter(
                customer_name__icontains=search
            )

    context = {
        "orders": orders,
        "delivery_status": delivery_status,
        "order_status": order_status,
        "search": search,
    }

    return render(
        request,
        "orders/fulfilment_dashboard.html",
        context,
    )


@staff_member_required
def fulfilment_order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related(
            "items__product",
            "status_history__changed_by",
        ),
        pk=pk,
    )

    history = order.status_history.all()

    return render(
        request,
        "orders/fulfilment_detail.html",
        {
            "order": order,
            "history": history,
        },
    )


@staff_member_required
def update_fulfilment_status(request, pk):
    if request.method != "POST":
        return redirect("orders:fulfilment_order_detail", pk=pk)

    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update(),
            pk=pk,
        )

        if order.status != "paid":
            messages.error(
                request,
                "Only paid orders can be dispatched or delivered.",
            )
            return redirect(
                "orders:fulfilment_order_detail",
                pk=pk,
            )

        new_status = request.POST.get("delivery_status", "")
        note = request.POST.get("note", "").strip()
        tracking_number = request.POST.get(
            "tracking_number",
            "",
        ).strip()

        allowed_transitions = {
            "processing": "shipped",
            "shipped": "delivered",
        }

        expected_status = allowed_transitions.get(
            order.delivery_status
        )

        if new_status != expected_status:
            messages.error(
                request,
                "Invalid status transition. Orders must move "
                "from Processing to Shipped, then Delivered.",
            )
            return redirect(
                "orders:fulfilment_order_detail",
                pk=pk,
            )

        previous_status = order.delivery_status
        order.delivery_status = new_status

        if new_status == "shipped":
            order.shipped_at = timezone.now()

            if tracking_number:
                order.tracking_number = tracking_number

        elif new_status == "delivered":
            order.delivered_at = timezone.now()

        order.save(
            update_fields=[
                "delivery_status",
                "shipped_at",
                "delivered_at",
                "tracking_number",
            ]
        )

        OrderStatusHistory.objects.create(
            order=order,
            previous_status=previous_status,
            new_status=new_status,
            changed_by=request.user,
            note=note,
        )

        # Schedule customer notification after successful commit.
        if new_status == "shipped":
            transaction.on_commit(
                lambda order_id=order.pk:
                    send_order_shipped_notification(order_id)
            )

        elif new_status == "delivered":
            transaction.on_commit(
                lambda order_id=order.pk:
                    send_order_delivered_notification(order_id)
            )

    messages.success(
        request,
        f"Order #{order.pk} updated to {order.get_delivery_status_display()}.",
    )

    return redirect(
        "orders:fulfilment_order_detail",
        pk=pk,
    )
