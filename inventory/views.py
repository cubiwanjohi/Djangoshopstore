import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Q,
    Sum,
)
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404

from store.models import Product

from .forms import StockAdjustmentForm, LowStockThresholdForm
from .models import StockMovement, InventorySettings
from .services import adjust_stock, InsufficientStockError

def staff_required(request):
    return request.user.is_staff


@login_required
def dashboard(request):
    """Display inventory information to authenticated staff members."""

    if not staff_required(request):
        return HttpResponseForbidden(
            "You do not have permission to access the inventory dashboard."
        )

    inventory_settings = InventorySettings.load()

    if request.method == "POST":
        threshold_form = LowStockThresholdForm(
            request.POST,
            instance=inventory_settings,
        )

        if threshold_form.is_valid():
            threshold_form.save()
            messages.success(
                request,
                "Low-stock threshold updated successfully.",
            )
            return redirect("inventory:dashboard")
    else:
        threshold_form = LowStockThresholdForm(
            instance=inventory_settings,
        )

    low_stock_threshold = inventory_settings.low_stock_threshold

    total_products = Product.objects.count()

    total_stock = (
        Product.objects.aggregate(total=Sum("stock"))["total"] or 0
    )

    low_stock_count = Product.objects.filter(
        stock__lte=low_stock_threshold
    ).count()

    low_stock_products = (
        Product.objects
        .filter(stock__lte=low_stock_threshold)
        .order_by("stock", "name")[:10]
    )

    recent_movements = (
        StockMovement.objects
        .select_related("product", "created_by", "order")
        .order_by("-created_at")[:10]
    )

    context = {
        "total_products": total_products,
        "total_stock": total_stock,
        "low_stock_count": low_stock_count,
        "low_stock_products": low_stock_products,
        "recent_movements": recent_movements,
        "low_stock_threshold": low_stock_threshold,
        "threshold_form": threshold_form,
    }

    return render(request, "inventory/dashboard.html", context)


@login_required
def stock_adjustment(request, movement_type):
    """Receive or remove stock and record the corresponding movement."""

    if not staff_required(request):
        return HttpResponseForbidden(
            "You do not have permission to adjust inventory."
        )

    if movement_type == StockMovement.MovementType.IN:
        page_title = "Receive Stock"
        button_text = "Receive Stock"

    elif movement_type == StockMovement.MovementType.OUT:
        page_title = "Remove Stock"
        button_text = "Remove Stock"

    else:
        return HttpResponseForbidden("Invalid stock movement type.")

    if request.method == "POST":
        form = StockAdjustmentForm(request.POST)

        if form.is_valid():
            try:
                adjust_stock(
                    product_id=form.cleaned_data["product"].pk,
                    movement_type=movement_type,
                    quantity=form.cleaned_data["quantity"],
                    note=form.cleaned_data["note"],
                    created_by=request.user,
                )

            except InsufficientStockError as error:
                form.add_error(None, str(error))

            except ValidationError as error:
                form.add_error(None, error)

            else:
                messages.success(
                    request,
                    f"Stock successfully updated for "
                    f"{form.cleaned_data['product'].name}.",
                )
                return redirect("inventory:dashboard")

    else:
        form = StockAdjustmentForm()

    context = {
        "form": form,
        "page_title": page_title,
        "button_text": button_text,
    }

    return render(
        request,
        "inventory/stock_adjustment.html",
        context,
    )


@login_required
def receive_stock(request):
    return stock_adjustment(
        request,
        StockMovement.MovementType.IN,
    )


@login_required
def remove_stock(request):
    return stock_adjustment(
        request,
        StockMovement.MovementType.OUT,
    )


@login_required
def movement_history(request):
    """Display all stock movements with product and type filters."""

    if not staff_required(request):
        return HttpResponseForbidden(
            "You do not have permission to view stock movement history."
        )

    movements = (
        StockMovement.objects
        .select_related("product", "created_by", "order")
        .all()
    )

    selected_product = request.GET.get("product", "")
    selected_type = request.GET.get("movement_type", "")

    if selected_product.isdigit():
        movements = movements.filter(product_id=int(selected_product))
    else:
        selected_product = ""

    valid_types = [
        value for value, label in StockMovement.MovementType.choices
    ]

    if selected_type in valid_types:
        movements = movements.filter(movement_type=selected_type)
    else:
        selected_type = ""

    context = {
        "movements": movements,
        "products": Product.objects.order_by("name"),
        "movement_types": StockMovement.MovementType.choices,
        "selected_product": selected_product,
        "selected_type": selected_type,
    }

    return render(
        request,
        "inventory/movement_history.html",
        context,
    )


@login_required
def product_stock_history(request, product_id):
    """Display the stock movement history of one product."""

    if not staff_required(request):
        return HttpResponseForbidden(
            "You do not have permission to view product stock history."
        )

    product = get_object_or_404(Product, pk=product_id)

    movements = (
        StockMovement.objects
        .filter(product=product)
        .select_related("created_by", "order")
        .order_by("-created_at")
    )

    context = {
        "product": product,
        "movements": movements,
    }

    return render(
        request,
        "inventory/product_stock_history.html",
        context,
    )


@login_required
def reports(request):
    """Display inventory reports for staff members."""

    if not staff_required(request):
        return HttpResponseForbidden(
            "You do not have permission to view inventory reports."
        )

    inventory_settings = InventorySettings.load()
    threshold = inventory_settings.low_stock_threshold

    # Product statistics
    product_stats = Product.objects.aggregate(
        total_products=Count("id"),
        total_stock=Sum("stock"),
        inventory_value=Sum(
            ExpressionWrapper(
                F("price") * F("stock"),
                output_field=DecimalField(
                    max_digits=18,
                    decimal_places=2,
                ),
            )
        ),
    )

    # Stock movement statistics
    movement_stats = StockMovement.objects.aggregate(
        total_received=Sum(
            "quantity",
            filter=Q(
                movement_type=StockMovement.MovementType.IN
            ),
        ),
        total_removed=Sum(
            "quantity",
            filter=Q(
                movement_type=StockMovement.MovementType.OUT
            ),
        ),
        total_reserved=Sum(
            "quantity",
            filter=Q(
                movement_type=StockMovement.MovementType.RESERVED
            ),
        ),
        total_returned=Sum(
            "quantity",
            filter=Q(
                movement_type=StockMovement.MovementType.RETURNED
            ),
        ),
    )

    low_stock_products = Product.objects.filter(
        stock__lte=threshold
    ).order_by("stock", "name")

    context = {
        "total_products": product_stats["total_products"] or 0,
        "total_stock": product_stats["total_stock"] or 0,
        "inventory_value": product_stats["inventory_value"] or 0,
        "total_received": movement_stats["total_received"] or 0,
        "total_removed": movement_stats["total_removed"] or 0,
        "total_reserved": movement_stats["total_reserved"] or 0,
        "total_returned": movement_stats["total_returned"] or 0,
        "low_stock_count": low_stock_products.count(),
        "low_stock_products": low_stock_products,
        "low_stock_threshold": threshold,
    }

    return render(
        request,
        "inventory/reports.html",
        context,
    )


@login_required
def export_inventory_csv(request):
    """Export the current inventory snapshot as a CSV file."""

    if not staff_required(request):
        return HttpResponseForbidden(
            "You do not have permission to export inventory reports."
        )

    inventory_settings = InventorySettings.load()
    threshold = inventory_settings.low_stock_threshold

    response = HttpResponse(
        content_type="text/csv; charset=utf-8"
    )

    response["Content-Disposition"] = (
        'attachment; filename="shopstore_inventory_report.csv"'
    )

    writer = csv.writer(response)

    writer.writerow([
        "Product",
        "Unit Price (KSh)",
        "Available Stock",
        "Stock Value (KSh)",
        "Low Stock Status",
    ])

    products = Product.objects.order_by("name")

    for product in products:
        stock_value = product.price * product.stock

        low_stock_status = (
            "LOW STOCK"
            if product.stock <= threshold
            else "NORMAL"
        )

        writer.writerow([
            product.name,
            product.price,
            product.stock,
            stock_value,
            low_stock_status,
        ])

    return response