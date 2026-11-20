
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from store.models import Order, Product

from .forms import ReviewForm
from .models import Review


@login_required
def create_review(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    # A customer must have a paid order containing this product.
    has_purchased = Order.objects.filter(
        user=request.user,
        status="paid",
        items__product=product,
    ).exists()

    if not has_purchased:
        messages.error(
            request,
            "You can only review products you have purchased and paid for.",
        )
        return redirect("product_detail", pk=product.pk)

    # Each customer may review a product only once.
    existing_review = Review.objects.filter(
        product=product,
        user=request.user,
    ).first()

    if existing_review:
        messages.info(
            request,
            "You have already reviewed this product. "
            "You can edit your review.",
        )
        return redirect(
            "reviews:edit_review",
            pk=existing_review.pk,
        )

    if request.method == "POST":
        form = ReviewForm(request.POST)

        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user

            try:
                # Protect the database write with a transaction.
                with transaction.atomic():
                    review.save()

            except IntegrityError:
                # Another request may have created this review first.
                existing_review = Review.objects.filter(
                    product=product,
                    user=request.user,
                ).first()

                if existing_review:
                    messages.info(
                        request,
                        "You have already reviewed this product. "
                        "You can edit your existing review.",
                    )
                    return redirect(
                        "reviews:edit_review",
                        pk=existing_review.pk,
                    )

                # If this was another database error,
                # do not silently suppress it.
                raise

            messages.success(
                request,
                "Your review has been submitted.",
            )
            return redirect(
                "product_detail",
                pk=product.pk,
            )

    else:
        form = ReviewForm()

    return render(
        request,
        "reviews/review_form.html",
        {
            "form": form,
            "product": product,
            "page_title": "Write a review",
        },
    )


@login_required
def edit_review(request, pk):
    review = get_object_or_404(
        Review,
        pk=pk,
        user=request.user,
    )

    if request.method == "POST":
        form = ReviewForm(request.POST, instance=review)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Your review has been updated.",
            )

            return redirect(
                "product_detail",
                pk=review.product_id,
            )

    else:
        form = ReviewForm(instance=review)

    return render(
        request,
        "reviews/review_form.html",
        {
            "form": form,
            "product": review.product,
            "review": review,
            "page_title": "Edit your review",
        },
    )


@login_required
@require_POST
def delete_review(request, pk):
    review = get_object_or_404(
        Review,
        pk=pk,
        user=request.user,
    )

    product_id = review.product_id
    review.delete()

    messages.success(
        request,
        "Your review has been deleted.",
    )

    return redirect(
        "product_detail",
        pk=product_id,
    )
