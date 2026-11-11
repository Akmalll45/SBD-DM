import json
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import LoginForm, RegisterForm
from .models import Cart, CartItem, Category, Order, OrderItem, Product, ProductVariant


def _safe_next(request):
    target = request.POST.get('next') or request.GET.get('next') or ''
    if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return reverse('store:home')


# -----------------------------------------------------------------------------
# AUTHENTICATION VIEWS
# -----------------------------------------------------------------------------

@require_http_methods(['GET', 'POST'])
def register_view(request):
    if request.user.is_authenticated:
        return redirect('store:home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        Cart.objects.create(user=user)
        login(request, user)
        messages.success(request, 'Akun berhasil dibuat. Selamat datang di Hendra Sport!')
        return redirect('store:home')

    return render(request, 'store/register.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(_safe_next(request))

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        messages.success(request, f'Selamat datang kembali, {request.user.username}!')
        return redirect(_safe_next(request))

    return render(request, 'store/login.html', {
        'form': form,
        'next': request.GET.get('next', ''),
    })


class LogoutUserView(LogoutView):
    next_page = 'store:login'


# -----------------------------------------------------------------------------
# CATALOG VIEWS
# -----------------------------------------------------------------------------

def home(request):
    """
    Homepage displaying minimalist hero banner, category explorer,
    featured jerseys, and new arrival collection.
    """
    categories = Category.objects.all()
    featured_products = (
        Product.objects.filter(is_featured=True)
        .prefetch_related('variants')
        .select_related('category')[:8]
    )
    latest_products = (
        Product.objects.all()
        .prefetch_related('variants')
        .select_related('category')[:4]
    )

    return render(request, 'store/home.html', {
        'categories': categories,
        'featured_products': featured_products,
        'latest_products': latest_products,
    })


def product_list(request):
    """
    Product listing page with category filters, keyword search, and sorting.
    """
    categories = Category.objects.all()
    products = (
        Product.objects.all()
        .prefetch_related('variants')
        .select_related('category')
    )

    # Filter by category
    selected_category_slug = request.GET.get('category', '').strip()
    active_category = None
    if selected_category_slug:
        active_category = get_object_or_404(Category, slug=selected_category_slug)
        products = products.filter(category=active_category)

    # Keyword search
    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        )

    # Sorting
    sort_by = request.GET.get('sort', 'newest')
    if sort_by == 'price_asc':
        products = products.order_by('base_price')
    elif sort_by == 'price_desc':
        products = products.order_by('-base_price')
    elif sort_by == 'name':
        products = products.order_by('name')
    else:
        products = products.order_by('-created_at')

    return render(request, 'store/product_list.html', {
        'products': products,
        'categories': categories,
        'active_category': active_category,
        'query': query,
        'sort_by': sort_by,
    })


def product_detail(request, slug):
    """
    Product detail page featuring high-res preview, size selector,
    and Custom Sablon toggling interface.
    """
    product = get_object_or_404(
        Product.objects.prefetch_related('variants').select_related('category'),
        slug=slug
    )
    related_products = (
        Product.objects.filter(category=product.category)
        .exclude(id=product.id)[:4]
    )

    return render(request, 'store/product_detail.html', {
        'product': product,
        'variants': product.variants.all(),
        'related_products': related_products,
        'sablon_fee': settings.SABLON_FEE,
    })


# -----------------------------------------------------------------------------
# CART & CHECKOUT VIEWS
# -----------------------------------------------------------------------------

@login_required(login_url='store:login')
def cart_detail(request):
    """
    Full-page cart view summarizing items, Sablon specifications, and subtotal.
    """
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product', 'variant')

    return render(request, 'store/cart.html', {
        'cart': cart,
        'items': items,
    })


@require_POST
def add_to_cart(request, product_id):
    """
    Add product variant to cart with optional Custom Sablon customization.
    Responds with standard redirect or JSON for sliding drawer.
    """
    if not request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'error': 'login_required', 'login_url': reverse('store:login')}, status=401)
        messages.info(request, 'Silakan login terlebih dahulu untuk menambahkan produk ke keranjang.')
        return redirect(f"{reverse('store:login')}?next={request.META.get('HTTP_REFERER', reverse('store:home'))}")

    product = get_object_or_404(Product, id=product_id)
    variant_id = request.POST.get('variant_id')
    if not variant_id:
        messages.error(request, 'Silakan pilih ukuran terlebih dahulu.')
        return redirect(request.META.get('HTTP_REFERER', reverse('store:home')))

    variant = get_object_or_404(ProductVariant, id=variant_id, product=product)

    try:
        quantity = max(1, int(request.POST.get('quantity', 1)))
    except (TypeError, ValueError):
        quantity = 1

    # Sablon parameters
    has_sablon = request.POST.get('has_sablon') in ('1', 'true', 'on', 'yes')
    custom_name = request.POST.get('custom_name', '').strip().upper()[:16] if has_sablon else ''
    custom_number_raw = request.POST.get('custom_number', '').strip() if has_sablon else ''
    custom_number = None
    if has_sablon and custom_number_raw.isdigit():
        custom_number = max(0, min(99, int(custom_number_raw)))

    cart, _ = Cart.objects.get_or_create(user=request.user)

    # Compute line key matching CartItem.save logic
    num_str = '' if custom_number is None else str(custom_number)
    line_key = f"{variant.id}|{int(has_sablon)}|{custom_name}|{num_str}"

    with transaction.atomic():
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            line_key=line_key,
            defaults={
                'product': product,
                'variant': variant,
                'quantity': quantity,
                'has_sablon': has_sablon,
                'custom_name': custom_name,
                'custom_number': custom_number,
            }
        )
        if not created:
            item.quantity += quantity
            item.save()

    # JSON response for AJAX sliding drawer
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        total_items = sum(i.quantity for i in cart.items.all())
        return JsonResponse({
            'success': True,
            'message': f"{product.name} ({variant.size}) ditambahkan ke keranjang.",
            'cart_items_count': total_items,
            'cart_total': float(cart.total),
        })

    messages.success(request, f"{product.name} ({variant.size}) berhasil ditambahkan ke keranjang.")
    return redirect('store:cart')


@require_POST
@login_required(login_url='store:login')
def update_cart_item(request, item_id):
    """
    Adjust quantity or remove item from cart.
    """
    cart = get_object_or_404(Cart, user=request.user)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)

    try:
        action = request.POST.get('action')
        if action == 'increase':
            item.quantity += 1
            item.save()
        elif action == 'decrease':
            if item.quantity > 1:
                item.quantity -= 1
                item.save()
            else:
                item.delete()
        elif action == 'remove':
            item.delete()
        else:
            new_qty = int(request.POST.get('quantity', 1))
            if new_qty > 0:
                item.quantity = new_qty
                item.save()
            else:
                item.delete()
    except (TypeError, ValueError):
        pass

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        total_items = sum(i.quantity for i in cart.items.all())
        return JsonResponse({
            'success': True,
            'cart_items_count': total_items,
            'cart_total': float(cart.total),
        })

    return redirect('store:cart')


@require_POST
@login_required(login_url='store:login')
def remove_cart_item(request, item_id):
    """
    Remove item from cart entirely.
    """
    cart = get_object_or_404(Cart, user=request.user)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    item.delete()

    messages.info(request, 'Produk dihapus dari keranjang.')
    return redirect('store:cart')


@login_required(login_url='store:login')
def checkout(request):
    """
    Checkout view to collect shipping details and convert cart into an order.
    """
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product', 'variant')

    if not items.exists():
        messages.warning(request, 'Keranjang belanja Anda masih kosong.')
        return redirect('store:shop')

    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        city = request.POST.get('city', '').strip()
        address = request.POST.get('address', '').strip()

        if not (full_name and phone and city and address):
            messages.error(request, 'Harap lengkapi semua data pengiriman.')
            return render(request, 'store/checkout.html', {'cart': cart, 'items': items})

        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                full_name=full_name,
                phone=phone,
                city=city,
                address=address,
                total=cart.total,
                status=Order.Status.PENDING,
            )

            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    variant=item.variant,
                    product_name=item.product.name,
                    size=item.variant.size if item.variant else '',
                    unit_price=item.unit_price,
                    quantity=item.quantity,
                    custom_name=item.custom_name,
                    custom_number=item.custom_number,
                    has_sablon=item.has_sablon,
                )

            # Clear cart items after successful checkout
            items.delete()

        messages.success(request, f'Pesanan #{order.id} berhasil dibuat!')
        return redirect('store:order_success', order_id=order.id)

    return render(request, 'store/checkout.html', {
        'cart': cart,
        'items': items,
    })


@login_required(login_url='store:login')
def order_success(request, order_id):
    """
    Confirmation screen after order placement.
    """
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'store/order_success.html', {
        'order': order,
    })
