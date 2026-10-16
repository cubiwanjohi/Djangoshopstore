"""Template context available on every page."""


def cart_summary(request):
    """Expose the number of items in the session cart for the header badge."""
    cart = request.session.get('cart', {})
    count = sum(qty for qty in cart.values() if isinstance(qty, int))
    return {'cart_count': count}