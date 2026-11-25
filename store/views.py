import json
import logging
import time
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LogoutView
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, FloatField, Q, Sum
from django.db.models.functions import Coalesce
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from dashboard.models import SiteSetting
from .forms import CheckoutShippingForm, LoginForm, PaymentProofForm, RegisterForm
from .invoices import render_invoice_pdf
from .models import (
    Cart,
    CartItem,
    Category,
    Order,
    OrderItem,
    Payment,
    Product,
    ProductRating,
    ProductVariant,
)
from .payments import (
    PaymentGatewayError,
    create_snap_transaction,
    mark_payment_paid,
    new_gateway_order_id,
    record_payment_status,
    release_order_stock,
    sync_midtrans_payment,
    verify_midtrans_signature,
)

logger = logging.getLogger(__name__)


def _available_payment_methods():
    methods = []
    if settings.MIDTRANS_SERVER_KEY and settings.MIDTRANS_CLIENT_KEY:
        methods.append((Payment.Method.MIDTRANS, Payment.Method.MIDTRANS.label))
    if all((
        settings.BANK_TRANSFER_NAME,
        settings.BANK_TRANSFER_ACCOUNT_NAME,
        settings.BANK_TRANSFER_ACCOUNT_NUMBER,
    )):
        methods.append((
            Payment.Method.MANUAL_TRANSFER,
            Payment.Method.MANUAL_TRANSFER.label,
        ))
    return methods


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
        user = form.get_user()
        from accounts.models import Profile

        profile, _ = Profile.objects.get_or_create(user=user)
        if profile.totp_enabled:
            request.session['pending_totp_user_id'] = user.pk
            request.session['pending_totp_next'] = _safe_next(request)
            request.session['pending_totp_created'] = int(time.time())
            return redirect('accounts:totp_login')

        login(request, user)
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
    featured jerseys (strictly jerseys only, top 4 by rating and cart additions),
    and new arrival collection.
    """
    categories = Category.objects.all()

    # Filter strictly jerseys only (exclude balls, equipment, accessories)
    jersey_filter = (
        Q(category__slug__in=['football-jerseys', 'other-sports-jerseys']) |
        Q(category__name__icontains='jersey') |
        Q(name__icontains='jersey')
    )

    # Top 4 jerseys based on user ratings and cart additions
    featured_products = (
        Product.objects.filter(jersey_filter)
        .annotate(
            annotated_avg_rating=Coalesce(Avg('ratings__rating'), 0.0, output_field=FloatField()),
            annotated_rating_count=Count('ratings', distinct=True),
            annotated_cart_additions=Count('cartitem', distinct=True),
        )
        .prefetch_related('variants', 'ratings')
        .select_related('category')
        .order_by(
            '-annotated_avg_rating',
            '-annotated_cart_additions',
            '-annotated_rating_count',
            '-is_featured',
            '-created_at',
        )[:4]
    )

    latest_products = (
        Product.objects.all()
        .annotate(
            annotated_avg_rating=Coalesce(Avg('ratings__rating'), 0.0, output_field=FloatField()),
            annotated_rating_count=Count('ratings', distinct=True),
        )
        .prefetch_related('variants', 'ratings')
        .select_related('category')[:4]
    )

    return render(request, 'store/home.html', {
        'categories': categories,
        'featured_products': featured_products,
        'latest_products': latest_products,
    })


def about(request):
    site_setting = SiteSetting.objects.filter(pk=1).first()
    contact_email = ''
    contact_phone = ''
    whatsapp_url = ''

    if site_setting:
        configured_email = (site_setting.contact_email or '').strip()
        if configured_email.lower() != 'support@hendrasport.com':
            contact_email = configured_email

        configured_phone = (site_setting.contact_phone or '').strip()
        phone_digits = ''.join(character for character in configured_phone if character.isdigit())
        if phone_digits and phone_digits != '6281234567890':
            contact_phone = configured_phone
            if phone_digits.startswith('0'):
                phone_digits = f'62{phone_digits[1:]}'
            if 8 <= len(phone_digits) <= 15:
                whatsapp_url = f'https://wa.me/{phone_digits}'

    return render(request, 'store/about.html', {
        'contact_email': contact_email,
        'contact_phone': contact_phone,
        'whatsapp_url': whatsapp_url,
    })


def product_list(request):
    """
    Product listing page with category filters, keyword search, rating annotations, and sorting.
    """
    categories = Category.objects.all()
    products = (
        Product.objects.all()
        .annotate(
            annotated_avg_rating=Coalesce(Avg('ratings__rating'), 0.0, output_field=FloatField()),
            annotated_rating_count=Count('ratings', distinct=True),
        )
        .prefetch_related('variants', 'ratings')
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
    elif sort_by == 'rating':
        products = products.order_by('-annotated_avg_rating', '-annotated_rating_count')
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
    Custom Sablon toggling interface, and user rating & reviews.
    """
    product = get_object_or_404(
        Product.objects.annotate(
            annotated_avg_rating=Coalesce(Avg('ratings__rating'), 0.0, output_field=FloatField()),
            annotated_rating_count=Count('ratings', distinct=True),
        ).prefetch_related('variants', 'ratings').select_related('category'),
        slug=slug
    )
    related_products = (
        Product.objects.filter(category=product.category)
        .exclude(id=product.id)
        .annotate(
            annotated_avg_rating=Coalesce(Avg('ratings__rating'), 0.0, output_field=FloatField()),
            annotated_rating_count=Count('ratings', distinct=True),
        )[:4]
    )

    user_rating = None
    if request.user.is_authenticated:
        user_rating = ProductRating.objects.filter(product=product, user=request.user).first()

    reviews = product.ratings.select_related('user').order_by('-created_at')
    variants = list(product.variants.all())
    default_variant = None
    if product.is_equipment:
        default_variant = next(
            (variant for variant in variants if variant.size.strip().upper() in ('ALL', 'ONE SIZE', 'ALL SIZE', 'OS', 'STANDAR')),
            variants[0] if variants else None,
        )

    return render(request, 'store/product_detail.html', {
        'product': product,
        'variants': variants,
        'default_variant': default_variant,
        'related_products': related_products,
        'sablon_fee': settings.SABLON_FEE,
        'user_rating': user_rating,
        'reviews': reviews,
    })


@require_POST
def rate_product(request, slug):
    """
    Submit or update product rating (1-5 stars) and optional review.
    Accessible to any logged-in user without purchase requirement.
    """
    if not request.user.is_authenticated:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'error': 'login_required',
                'message': 'Silakan masuk terlebih dahulu untuk memberi penilaian.'
            }, status=401)
        messages.info(request, 'Silakan masuk terlebih dahulu untuk memberi penilaian.')
        return redirect(f"{reverse('store:login')}?next={reverse('store:product_detail', kwargs={'slug': slug})}")

    product = get_object_or_404(Product, slug=slug)

    try:
        rating_val = int(request.POST.get('rating', 0))
    except (ValueError, TypeError):
        rating_val = 0

    if rating_val < 1 or rating_val > 5:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Pilih jumlah bintang dari 1 hingga 5.'
            }, status=400)
        messages.error(request, 'Pilih jumlah bintang dari 1 hingga 5.')
        return redirect('store:product_detail', slug=slug)

    review_text = request.POST.get('review', '').strip()

    rating_obj, created = ProductRating.objects.update_or_create(
        product=product,
        user=request.user,
        defaults={
            'rating': rating_val,
            'review': review_text,
        }
    )

    action_msg = 'Terima kasih! Penilaian Anda berhasil dikirim.' if created else 'Penilaian Anda berhasil diperbarui.'

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        agg = product.ratings.aggregate(
            avg=Avg('rating'),
            count=Count('id')
        )
        return JsonResponse({
            'success': True,
            'message': action_msg,
            'rating': rating_val,
            'review': review_text,
            'avg_rating': round(agg['avg'], 1) if agg['avg'] else 0.0,
            'total_ratings': agg['count'],
        })

    messages.success(request, action_msg)
    return redirect('store:product_detail', slug=slug)


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
        # Auto-fallback to single variant if equipment or only 1 variant exists
        single_variant = product.variants.first()
        if single_variant and (product.has_single_size or product.variants.count() == 1):
            variant = single_variant
        else:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Silakan pilih ukuran terlebih dahulu.'}, status=400)
            messages.error(request, 'Silakan pilih ukuran terlebih dahulu.')
            return redirect(request.META.get('HTTP_REFERER', reverse('store:home')))
    else:
        variant = get_object_or_404(ProductVariant, id=variant_id, product=product)

    try:
        quantity = max(1, int(request.POST.get('quantity', 1)))
    except (TypeError, ValueError):
        quantity = 1

    # Sablon parameters - strictly only permitted for jerseys with allow_custom_print
    if product.allow_custom_print and product.is_jersey:
        has_sablon = request.POST.get('has_sablon') in ('1', 'true', 'on', 'yes')
        custom_name = request.POST.get('custom_name', '').strip().upper()[:16] if has_sablon else ''
        custom_number_raw = request.POST.get('custom_number', '').strip() if has_sablon else ''
        custom_number = None
        if has_sablon and custom_number_raw.isdigit():
            custom_number = max(0, min(99, int(custom_number_raw)))
    else:
        has_sablon = False
        custom_name = ''
        custom_number = None

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
    cart_message = product.name
    if not product.is_equipment:
        cart_message = f'{cart_message} ({variant.size})'

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        total_items = sum(i.quantity for i in cart.items.all())
        return JsonResponse({
            'success': True,
            'message': f'{cart_message} ditambahkan ke keranjang.',
            'cart_items_count': total_items,
            'cart_total': float(cart.total),
        })

    messages.success(request, f'{cart_message} berhasil ditambahkan ke keranjang.')
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
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = list(cart.items.select_related('product', 'variant').order_by('pk'))

    if not items:
        messages.warning(request, 'Keranjang belanja Anda masih kosong.')
        return redirect('store:shop')

    from accounts.models import Address, Profile

    profile, _ = Profile.objects.get_or_create(user=request.user)
    primary_address = Address.objects.filter(user=request.user, is_primary=True).first()
    shipping_initial = {
        'full_name': request.user.get_full_name() or request.user.username,
        'phone': profile.phone,
        'city': '',
        'address': '',
    }
    if primary_address:
        shipping_initial.update({
            'full_name': primary_address.recipient_name,
            'phone': primary_address.recipient_phone,
            'city': primary_address.city,
            'address': ', '.join(filter(None, [
                primary_address.detail_address,
                primary_address.subdistrict,
                primary_address.district,
                primary_address.province,
                primary_address.postal_code,
            ])),
        })

    form = CheckoutShippingForm(
        request.POST or None,
        initial=shipping_initial,
        shipping_options=settings.CHECKOUT_SHIPPING_OPTIONS,
    )
    if request.method == 'POST' and form.is_valid():
        request.session['checkout_shipping'] = form.cleaned_data
        return redirect('store:checkout_confirm')

    return render(request, 'store/checkout.html', {
        'cart': cart,
        'items': items,
        'form': form,
        'shipping_initial': shipping_initial,
        'items_subtotal': sum((item.line_total for item in items), Decimal('0')),
    })


@login_required(login_url='store:login')
@require_http_methods(['GET', 'POST'])
def checkout_confirm(request):
    shipping_data = request.session.get('checkout_shipping')
    if not isinstance(shipping_data, dict):
        messages.warning(request, 'Lengkapi informasi pengiriman terlebih dahulu.')
        return redirect('store:checkout')

    shipping_form = CheckoutShippingForm(
        data=shipping_data,
        shipping_options=settings.CHECKOUT_SHIPPING_OPTIONS,
    )
    if not shipping_form.is_valid():
        request.session.pop('checkout_shipping', None)
        messages.error(request, 'Data pengiriman tidak valid. Silakan isi kembali.')
        return redirect('store:checkout')
    shipping_data = shipping_form.cleaned_data

    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = list(cart.items.select_related('product', 'variant').order_by('pk'))
    if not items:
        messages.warning(request, 'Keranjang belanja Anda masih kosong.')
        return redirect('store:shop')

    shipping_options = {
        code: (label, amount)
        for code, label, amount in settings.CHECKOUT_SHIPPING_OPTIONS
    }
    courier_label, configured_shipping_cost = shipping_options[shipping_data['courier']]
    free_shipping = all(item.product.free_shipping for item in items)
    shipping_cost = 0 if free_shipping else configured_shipping_cost
    items_subtotal = sum((item.line_total for item in items), Decimal('0'))
    payment_methods = _available_payment_methods()

    if request.method == 'POST':
        payment_method = request.POST.get('payment_method')
        if payment_method not in [method for method, _ in payment_methods]:
            messages.error(
                request,
                'Metode pembayaran belum tersedia atau belum dikonfigurasi oleh admin.',
            )
        else:
            try:
                with transaction.atomic():
                    locked_cart = Cart.objects.select_for_update().get(pk=cart.pk)
                    locked_items = list(
                        CartItem.objects.select_for_update()
                        .filter(cart=locked_cart)
                        .order_by('pk')
                    )
                    if not locked_items:
                        raise ValidationError('Keranjang belanja Anda masih kosong.')

                    product_ids = sorted({item.product_id for item in locked_items})
                    variant_ids = sorted({item.variant_id for item in locked_items})
                    products = {
                        product.pk: product
                        for product in Product.objects.select_for_update()
                        .filter(pk__in=product_ids)
                        .order_by('pk')
                    }
                    variants = {
                        variant.pk: variant
                        for variant in ProductVariant.objects.select_for_update()
                        .filter(pk__in=variant_ids)
                        .order_by('pk')
                    }
                    quantities = {}
                    for item in locked_items:
                        item.product = products.get(item.product_id)
                        item.variant = variants.get(item.variant_id)
                        if not item.product or not item.variant:
                            raise ValidationError('Produk dalam keranjang sudah tidak tersedia.')
                        quantities[item.variant_id] = (
                            quantities.get(item.variant_id, 0) + item.quantity
                        )

                    for variant_id, quantity in quantities.items():
                        if variants[variant_id].stock < quantity:
                            stock_label = 'produk' if variants[variant_id].product.is_equipment else (
                                f'ukuran {variants[variant_id].size}'
                            )
                            raise ValidationError(
                                f'Stok {stock_label} '
                                f'untuk {variants[variant_id].product.name} tidak mencukupi.'
                            )

                    subtotal = sum(
                        (item.unit_price * item.quantity for item in locked_items),
                        Decimal('0'),
                    )
                    free_shipping_now = all(item.product.free_shipping for item in locked_items)
                    final_shipping_cost = (
                        0 if free_shipping_now else configured_shipping_cost
                    )
                    total_amount = subtotal + Decimal(final_shipping_cost)
                    if total_amount > Decimal('999999999999'):
                        raise ValidationError('Total pembayaran melebihi batas transaksi yang didukung.')
                    order = Order.objects.create(
                        user=request.user,
                        full_name=shipping_data['full_name'],
                        phone=shipping_data['phone'],
                        city=shipping_data['city'],
                        address=shipping_data['address'],
                        courier=courier_label,
                        shipping_cost=final_shipping_cost,
                        total=total_amount,
                        status=Order.Status.PENDING,
                        stock_reserved_at=timezone.now(),
                    )

                    for item in locked_items:
                        OrderItem.objects.create(
                            order=order,
                            product=item.product,
                            variant=item.variant,
                            product_name=item.product.name,
                            size=item.variant.size,
                            unit_price=item.unit_price,
                            sablon_fee=(
                                Decimal(str(settings.SABLON_FEE))
                                if item.has_sablon
                                else Decimal('0')
                            ),
                            quantity=item.quantity,
                            custom_name=item.custom_name,
                            custom_number=item.custom_number,
                            has_sablon=item.has_sablon,
                        )

                    for variant_id, quantity in quantities.items():
                        variant = variants[variant_id]
                        variant.stock -= quantity
                        variant.save(update_fields=['stock'])

                    for product in products.values():
                        product.stock = (
                            ProductVariant.objects.filter(product=product)
                            .aggregate(total=Sum('stock'))['total']
                            or 0
                        )
                        product.save(update_fields=['stock'])

                    payment = Payment.objects.create(
                        order=order,
                        method=payment_method,
                        status=Payment.Status.PENDING,
                        amount=order.total,
                        gateway_order_id=(
                            new_gateway_order_id(order.pk)
                            if payment_method == Payment.Method.MIDTRANS
                            else None
                        ),
                    )
                    record_payment_status(payment, 'Menunggu pembayaran.')
                    CartItem.objects.filter(cart=locked_cart).delete()
            except ValidationError as exc:
                messages.error(request, ' '.join(exc.messages))
                return redirect('store:cart')

            request.session.pop('checkout_shipping', None)
            return redirect('store:payment_detail', order_id=order.pk)

    return render(request, 'store/checkout_confirm.html', {
        'cart': cart,
        'items': items,
        'shipping': shipping_data,
        'courier_label': courier_label,
        'shipping_cost': shipping_cost,
        'free_shipping': free_shipping,
        'items_subtotal': items_subtotal,
        'total': items_subtotal + shipping_cost,
        'payment_methods': payment_methods,
    })


@login_required(login_url='store:login')
@require_http_methods(['GET', 'POST'])
def payment_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('payment', 'user').prefetch_related(
            'items',
            'payment__status_history__actor',
        ),
        pk=order_id,
        user=request.user,
    )
    payment = order.payment
    payment_methods = _available_payment_methods()

    if request.method == 'POST' and request.POST.get('action') == 'select_method':
        selected_method = request.POST.get('payment_method')
        with transaction.atomic():
            locked_order = Order.objects.select_for_update().get(pk=order.pk)
            locked_payment = Payment.objects.select_for_update().get(order=locked_order)
            if (
                locked_payment.method != Payment.Method.LEGACY
                or locked_payment.status != Payment.Status.PENDING
                or locked_order.status != Order.Status.PENDING
                or selected_method not in [method for method, _ in payment_methods]
            ):
                messages.error(request, 'Metode pembayaran tidak dapat diubah pada pesanan ini.')
                return redirect('store:payment_detail', order_id=order.pk)
            locked_payment.method = selected_method
            locked_payment.gateway_order_id = (
                new_gateway_order_id(locked_order.pk)
                if selected_method == Payment.Method.MIDTRANS
                else None
            )
            locked_payment.save(update_fields=[
                'method',
                'gateway_order_id',
                'updated_at',
            ])
            record_payment_status(
                locked_payment,
                f'Metode pembayaran dipilih: {locked_payment.get_method_display()}.',
            )
        return redirect('store:payment_detail', order_id=order.pk)

    if request.method == 'POST' and request.POST.get('action') == 'retry_midtrans':
        with transaction.atomic():
            locked_order = Order.objects.select_for_update().get(pk=order.pk)
            locked_payment = Payment.objects.select_for_update().get(order=locked_order)
            if (
                locked_payment.method != Payment.Method.MIDTRANS
                or locked_payment.status != Payment.Status.FAILED
                or locked_order.status != Order.Status.PENDING
            ):
                messages.error(request, 'Tagihan ini tidak dapat dibuat ulang.')
                return redirect('store:payment_detail', order_id=order.pk)
            locked_payment.status = Payment.Status.PENDING
            locked_payment.gateway_order_id = new_gateway_order_id(locked_order.pk)
            locked_payment.gateway_transaction_id = None
            locked_payment.snap_token = ''
            locked_payment.snap_redirect_url = ''
            locked_payment.save(update_fields=[
                'status',
                'gateway_order_id',
                'gateway_transaction_id',
                'snap_token',
                'snap_redirect_url',
                'updated_at',
            ])
            record_payment_status(
                locked_payment,
                'Tagihan Midtrans baru dibuat setelah pembayaran sebelumnya gagal.',
            )
        return redirect('store:payment_detail', order_id=order.pk)

    proof_form = PaymentProofForm()
    if request.method == 'POST' and request.POST.get('action') == 'submit_proof':
        proof_form = PaymentProofForm(request.POST, request.FILES)
        if proof_form.is_valid():
            with transaction.atomic():
                locked_order = Order.objects.select_for_update().get(pk=order.pk)
                locked_payment = Payment.objects.select_for_update().get(order=locked_order)
                if (
                    locked_payment.method != Payment.Method.MANUAL_TRANSFER
                    or locked_payment.status not in (
                        Payment.Status.PENDING,
                        Payment.Status.FAILED,
                    )
                    or locked_order.status != Order.Status.PENDING
                    or not all((
                        settings.BANK_TRANSFER_NAME,
                        settings.BANK_TRANSFER_ACCOUNT_NAME,
                        settings.BANK_TRANSFER_ACCOUNT_NUMBER,
                    ))
                ):
                    messages.error(
                        request,
                        'Bukti transfer tidak dapat dikirim atau instruksi rekening belum tersedia.',
                    )
                else:
                    locked_payment.proof = proof_form.cleaned_data['proof']
                    locked_payment.proof_submitted_at = timezone.now()
                    locked_payment.status = Payment.Status.AWAITING_VERIFICATION
                    locked_payment.rejection_note = ''
                    locked_payment.verified_by = None
                    locked_payment.verified_at = None
                    locked_payment.save(update_fields=[
                        'proof',
                        'proof_submitted_at',
                        'status',
                        'rejection_note',
                        'verified_by',
                        'verified_at',
                        'updated_at',
                    ])
                    record_payment_status(
                        locked_payment,
                        'Bukti transfer dikirim dan menunggu verifikasi admin.',
                    )
                    messages.success(request, 'Bukti transfer terkirim dan menunggu verifikasi admin.')
                    return redirect('store:payment_detail', order_id=order.pk)
        else:
            messages.error(request, 'Periksa kembali file bukti transfer yang dipilih.')

    gateway_error = ''
    snap_token = ''
    if (
        payment.method == Payment.Method.MIDTRANS
        and payment.status == Payment.Status.PENDING
    ):
        try:
            snap_token = create_snap_transaction(payment)
        except PaymentGatewayError as exc:
            gateway_error = str(exc)
            logger.warning('Unable to create Snap transaction for order #%s: %s', order.pk, exc)

    return render(request, 'store/payment_detail.html', {
        'order': order,
        'payment': payment,
        'payment_history': list(payment.status_history.all()),
        'proof_form': proof_form,
        'snap_token': snap_token,
        'gateway_error': gateway_error,
        'midtrans_client_key': settings.MIDTRANS_CLIENT_KEY,
        'bank_transfer_name': settings.BANK_TRANSFER_NAME,
        'bank_transfer_account_name': settings.BANK_TRANSFER_ACCOUNT_NAME,
        'bank_transfer_account_number': settings.BANK_TRANSFER_ACCOUNT_NUMBER,
        'payment_methods': payment_methods,
    })


@csrf_exempt
@require_POST
def midtrans_notification(request):
    if len(request.body) > 65536:
        return HttpResponse(status=413)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': 'invalid_json'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'error': 'invalid_payload'}, status=400)
    if not all(
        isinstance(payload.get(key), str)
        for key in ('order_id', 'status_code', 'gross_amount', 'signature_key')
    ):
        return JsonResponse({'error': 'invalid_payload'}, status=400)
    if len(payload['order_id']) > 64 or not verify_midtrans_signature(payload):
        return JsonResponse({'error': 'invalid_signature'}, status=403)

    gateway_order_id = payload.get('order_id', '')
    try:
        payment = Payment.objects.get(gateway_order_id=gateway_order_id)
    except Payment.DoesNotExist:
        return JsonResponse({'error': 'payment_not_found'}, status=404)

    try:
        gross_amount = Decimal(str(payload.get('gross_amount', '')))
    except InvalidOperation:
        return JsonResponse({'error': 'invalid_amount'}, status=400)
    if not gross_amount.is_finite() or gross_amount != payment.amount:
        return JsonResponse({'error': 'amount_mismatch'}, status=400)

    transaction_status = payload.get('transaction_status')
    fraud_status = payload.get('fraud_status')
    transaction_id = payload.get('transaction_id') or None
    if (
        not isinstance(transaction_status, str)
        or (fraud_status is not None and not isinstance(fraud_status, str))
        or (transaction_id is not None and not isinstance(transaction_id, str))
        or (transaction_id is not None and len(transaction_id) > 100)
    ):
        return JsonResponse({'error': 'invalid_payload'}, status=400)

    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.gateway_order_id != gateway_order_id:
            return JsonResponse({'error': 'payment_reference_changed'}, status=409)
        if payment.method != Payment.Method.MIDTRANS:
            return JsonResponse({'error': 'invalid_payment_method'}, status=400)
        if gross_amount != payment.amount:
            return JsonResponse({'error': 'amount_mismatch'}, status=400)
        if payment.status == Payment.Status.PAID:
            return JsonResponse({'ok': True})
        if transaction_id and Payment.objects.filter(
            gateway_transaction_id=transaction_id
        ).exclude(pk=payment.pk).exists():
            return JsonResponse({'error': 'duplicate_transaction'}, status=409)

        if transaction_status == 'settlement' or (
            transaction_status == 'capture' and fraud_status == 'accept'
        ):
            if transaction_id:
                payment.gateway_transaction_id = transaction_id
                payment.save(update_fields=['gateway_transaction_id', 'updated_at'])
            mark_payment_paid(payment)
        elif transaction_status == 'pending':
            return JsonResponse({'ok': True})
        elif transaction_status in ('expire', 'cancel', 'deny'):
            previous_status = payment.status
            payment.status = (
                Payment.Status.EXPIRED
                if transaction_status == 'expire'
                else Payment.Status.CANCELLED
                if transaction_status == 'cancel'
                else Payment.Status.FAILED
            )
            if transaction_id:
                payment.gateway_transaction_id = transaction_id
            payment.save(update_fields=[
                'status',
                'gateway_transaction_id',
                'updated_at',
            ])
            if payment.status != previous_status:
                status_notes = {
                    'expire': 'Tagihan Midtrans kedaluwarsa.',
                    'cancel': 'Transaksi Midtrans dibatalkan.',
                    'deny': 'Transaksi Midtrans ditolak.',
                }
                record_payment_status(payment, status_notes[transaction_status])
            if transaction_status in ('expire', 'cancel'):
                order = Order.objects.select_for_update().get(pk=payment.order_id)
                if order.status == Order.Status.PENDING:
                    order.status = Order.Status.CANCELLED
                    order.save(update_fields=['status'])
                release_order_stock(order)
        elif transaction_status in ('refund', 'partial_refund'):
            if (
                transaction_status == 'refund'
                and payment.status != Payment.Status.REFUNDED
            ):
                payment.status = Payment.Status.REFUNDED
                payment.save(update_fields=['status', 'updated_at'])
                record_payment_status(payment, 'Pembayaran dikembalikan oleh Midtrans.')

    return JsonResponse({'ok': True})


@login_required(login_url='store:login')
def payment_proof_file(request, order_id):
    order_filter = {'order_id': order_id}
    if not request.user.is_staff:
        order_filter['order__user'] = request.user
    payment = get_object_or_404(
        Payment.objects.select_related('order'),
        **order_filter,
    )
    if not payment.proof:
        return HttpResponse(status=404)
    file_handle = payment.proof.open('rb')
    extension = payment.proof.name.rpartition('.')[2].lower()
    content_type = {
        'pdf': 'application/pdf',
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
    }[extension]
    response = FileResponse(
        file_handle,
        as_attachment=True,
        filename=f'bukti-transfer-{order_id}.{extension}',
        content_type=content_type,
    )
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required(login_url='store:login')
def invoice_pdf(request, order_id):
    order_filter = {'pk': order_id}
    if not request.user.is_staff:
        order_filter['user'] = request.user
    order = get_object_or_404(
        Order.objects.select_related('user', 'payment').prefetch_related('items'),
        **order_filter,
    )
    response = FileResponse(
        render_invoice_pdf(order),
        as_attachment=request.GET.get('print') != '1',
        filename=f'invoice-hendra-sport-{order.pk}.pdf',
        content_type='application/pdf',
    )
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required(login_url='store:login')
def order_success(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('payment').prefetch_related('items'),
        pk=order_id,
        user=request.user,
    )
    # Auto-sync with Midtrans in case customer just completed payment
    payment = getattr(order, 'payment', None)
    if payment and payment.method == Payment.Method.MIDTRANS and payment.status != Payment.Status.PAID:
        sync_midtrans_payment(payment)
        order.refresh_from_db()
        order.payment.refresh_from_db()

    return render(request, 'store/order_success.html', {
        'order': order,
    })


@login_required(login_url='store:login')
@require_POST
def sync_order_payment(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('payment'),
        pk=order_id,
        user=request.user,
    )
    payment = getattr(order, 'payment', None)
    if not payment:
        return JsonResponse({'success': False, 'message': 'Data pembayaran tidak ditemukan.'}, status=404)

    is_paid = sync_midtrans_payment(payment)
    return JsonResponse({
        'success': True,
        'is_paid': is_paid,
        'payment_status': payment.status,
        'payment_status_display': payment.get_status_display(),
        'order_status': order.status,
        'order_status_display': order.get_status_display(),
    })
