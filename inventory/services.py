
from django.core.exceptions import ValidationError
from django.db import transaction

from store.models import Product

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
    adjusted stock, such as checkout or payment restoration.
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
    Checkout reservations and payment returns use
    record_stock_movement instead.
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
