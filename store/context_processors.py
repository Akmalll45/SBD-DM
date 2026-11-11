from decimal import Decimal
from django.conf import settings
from .models import Cart


def cart_context(request):
    """
    Exposes cart summary across all templates for navbar and sliding drawer.
    """
    cart = None
    cart_items_count = 0
    cart_total = Decimal('0')

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        cart_items_count = sum(item.quantity for item in cart.items.all())
        cart_total = cart.total

    return {
        'cart': cart,
        'cart_items_count': cart_items_count,
        'cart_total': cart_total,
        'SABLON_FEE': getattr(settings, 'SABLON_FEE', 75000),
    }

