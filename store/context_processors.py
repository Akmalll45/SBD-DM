from decimal import Decimal
from django.conf import settings
from .models import Cart


def cart_context(request):
    """
    Exposes cart summary across all templates for navbar and sliding drawer.
    Uses select_related to avoid N+1 queries on every page load.
    """
    cart = None
    cart_items = []
    cart_items_count = 0
    cart_total = Decimal('0')

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_items = list(
            cart.items.select_related('product', 'variant').order_by('pk')
        )
        cart_items_count = sum(item.quantity for item in cart_items)
        cart_total = sum((item.line_total for item in cart_items), Decimal('0'))

    return {
        'cart': cart,
        'cart_items': cart_items,
        'cart_items_count': cart_items_count,
        'cart_total': cart_total,
        'SABLON_FEE': getattr(settings, 'SABLON_FEE', 20000),
    }

