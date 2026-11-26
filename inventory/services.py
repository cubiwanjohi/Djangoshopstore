
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum

from store.models import Order, Product

from .models import StockMovement


class InsufficientStockError(ValueError):
    """Raised when an operation tries to remove more stock than available."""


def record_stock_movement(
    *,
    product,
    movement_type,
    quantity,
    order=None,
    note="",
    created_by=None,
):
    """
    Record a stock movement without changing Product.stock.

    Use this when another part of the application has already
    adjusted stock, such as checkout.
    """

    if quantity < 1:
        raise ValidationError("Movement quantity must be at least 1.")

    return StockMovement.objects.create(
        product=product,
        movement_type=movement_type,
        quantity=quantity,
        order=order,
        note=note,
        created_by=created_by,
    )


@transaction.atomic
def restore_reserved_stock(*, order, note):
    """
    Restore outstanding stock reservations for an order exactly once.

    The order row is locked so concurrent restoration attempts for the
    same order cannot both restore the same reserved quantity.

    Only quantities recorded as RESERVED are eligible for restoration.
    Previously returned quantities are subtracted.
    """

    # Serialize restoration attempts for this order.
    Order.objects.select_for_update().get(pk=order.pk)

    reserved = (
        StockMovement.objects.filter(
            order=order,
            movement_type=StockMovement.MovementType.RESERVED,
        )
        .values("product_id")
        .annotate(total=Sum("quantity"))
        .order_by("product_id")
    )

    restored_movements = []

    for reservation in reserved:
        product_id = reservation["product_id"]
        reserved_quantity = reservation["total"]

        already_returned = (
            StockMovement.objects.filter(
                order=order,
                product_id=product_id,
                movement_type=StockMovement.MovementType.RETURNED,
            ).aggregate(total=Sum("quantity"))["total"]
            or 0
        )

        outstanding_quantity = reserved_quantity - already_returned

        if outstanding_quantity <= 0:
            continue

        # Lock the product before updating its stock.
        product = Product.objects.select_for_update().get(pk=product_id)

        Product.objects.filter(pk=product_id).update(
            stock=F("stock") + outstanding_quantity
        )

        movement = record_stock_movement(
            product=product,
            order=order,
            movement_type=StockMovement.MovementType.RETURNED,
            quantity=outstanding_quantity,
            note=note,
        )

        restored_movements.append(movement)

    return restored_movements


@transaction.atomic
def adjust_stock(
    *,
    product_id,
    movement_type,
    quantity,
    note="",
    created_by=None,
):
    """
    Adjust product stock and record the movement atomically.

    This function is for manual stock receipts and removals.
    Checkout reservations and payment returns use dedicated services.
    """

    if quantity < 1:
        raise ValidationError("Movement quantity must be at least 1.")

    if movement_type not in (
        StockMovement.MovementType.IN,
        StockMovement.MovementType.OUT,
    ):
        raise ValidationError(
            "Only IN and OUT movements can use adjust_stock()."
        )

    product = Product.objects.select_for_update().get(pk=product_id)

    if movement_type == StockMovement.MovementType.IN:
        product.stock += quantity

    elif movement_type == StockMovement.MovementType.OUT:
        if product.stock < quantity:
            raise InsufficientStockError(
                f"Cannot remove {quantity} units of {product.name}. "
                f"Only {product.stock} units are available."
            )

        product.stock -= quantity

    product.save(update_fields=["stock"])

    movement = StockMovement.objects.create(
        product=product,
        movement_type=movement_type,
        quantity=quantity,
        note=note,
        created_by=created_by,
    )

    return movement
