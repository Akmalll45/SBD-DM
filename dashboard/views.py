from decimal import Decimal
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from store.models import Category, Order, OrderItem, Product, ProductVariant
from .forms import ArticleForm, OrderStatusForm, ProductForm, SiteSettingForm
from .models import Article, SiteSetting


# -----------------------------------------------------------------------------
# 1. OVERVIEW & ANALYTICS DASHBOARD
# -----------------------------------------------------------------------------

@staff_member_required(login_url='store:login')
def admin_dashboard(request):
    """
    Main Analytics Overview: Total Revenue, Total Orders, Active Customers,
    Low Stock Alerts, Sablon Production metrics, and Recent Orders.
    """
    # 1. Revenue: Completed / non-cancelled orders
    valid_orders = Order.objects.exclude(status=Order.Status.CANCELLED)
    total_revenue = valid_orders.aggregate(total=Sum('total'))['total'] or Decimal('0')

    # 2. Orders summary
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status=Order.Status.PENDING).count()
    paid_orders = Order.objects.filter(status=Order.Status.PAID).count()
    shipped_orders = Order.objects.filter(status=Order.Status.SHIPPED).count()

    # 3. Customer base
    total_customers = User.objects.filter(is_staff=False).count()

    # 4. Custom Sablon Production Metrics (Key revenue driver)
    total_sablon_orders = OrderItem.objects.filter(has_sablon=True).count()
    setting = SiteSetting.load()
    sablon_revenue_est = total_sablon_orders * setting.sablon_fee

    # 5. Low Stock Alerts (variants with stock <= 5)
    low_stock_variants = (
        ProductVariant.objects.filter(stock__lte=5)
        .select_related('product', 'product__category')
        .order_by('stock')[:8]
    )

    # 6. Recent Orders
    recent_orders = (
        Order.objects.all()
        .select_related('user')
        .prefetch_related('items')
        .order_by('-created_at')[:8]
    )

    # 7. Total Products
    total_products = Product.objects.count()

    return render(request, 'dashboard/dashboard.html', {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'paid_orders': paid_orders,
        'shipped_orders': shipped_orders,
        'total_customers': total_customers,
        'total_sablon_orders': total_sablon_orders,
        'sablon_revenue_est': sablon_revenue_est,
        'low_stock_variants': low_stock_variants,
        'recent_orders': recent_orders,
        'total_products': total_products,
        'site_setting': setting,
    })


# -----------------------------------------------------------------------------
# 2. SITE SETTINGS & BRAND CMS
# -----------------------------------------------------------------------------

@staff_member_required(login_url='store:login')
def site_settings(request):
    """
    Manage site brand name, contact info, logo file, and sablon pricing fee.
    """
    setting = SiteSetting.load()
    form = SiteSettingForm(request.POST or None, request.FILES or None, instance=setting)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Pengaturan identitas toko berhasil diperbarui!')
        return redirect('dashboard:site_settings')

    return render(request, 'dashboard/site_settings.html', {
        'form': form,
        'setting': setting,
    })


# -----------------------------------------------------------------------------
# 3. ORDER MANAGEMENT & SABLON PROCESSING
# -----------------------------------------------------------------------------

@staff_member_required(login_url='store:login')
def order_list(request):
    """
    Order list with status filtering (pending, paid, shipped, cancelled) and search.
    """
    orders = Order.objects.select_related('user').prefetch_related('items').order_by('-created_at')

    status_filter = request.GET.get('status', '').strip()
    if status_filter:
        orders = orders.filter(status=status_filter)

    search_query = request.GET.get('q', '').strip()
    if search_query:
        orders = orders.filter(
            Q(id__icontains=search_query) |
            Q(full_name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(city__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )

    # Status counts for tabs
    counts = {
        'all': Order.objects.count(),
        'pending': Order.objects.filter(status=Order.Status.PENDING).count(),
        'paid': Order.objects.filter(status=Order.Status.PAID).count(),
        'shipped': Order.objects.filter(status=Order.Status.SHIPPED).count(),
        'cancelled': Order.objects.filter(status=Order.Status.CANCELLED).count(),
    }

    return render(request, 'dashboard/order_list.html', {
        'orders': orders,
        'status_filter': status_filter,
        'search_query': search_query,
        'counts': counts,
    })


@staff_member_required(login_url='store:login')
def order_detail(request, order_id):
    """
    Detailed Order View with customer shipping info, item breakdown,
    prominent Custom Sablon highlights, and status update controller.
    """
    order = get_object_or_404(
        Order.objects.select_related('user').prefetch_related('items', 'items__product'),
        id=order_id
    )

    if request.method == 'POST':
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, f'Status pesanan #{order.id} berhasil diubah menjadi {order.get_status_display()}.')
            return redirect('dashboard:order_detail', order_id=order.id)
    else:
        form = OrderStatusForm(instance=order)

    # Check how many items include custom sablon
    has_any_sablon = order.items.filter(has_sablon=True).exists()

    return render(request, 'dashboard/order_detail.html', {
        'order': order,
        'form': form,
        'has_any_sablon': has_any_sablon,
    })


# -----------------------------------------------------------------------------
# 4. PRODUCT & INVENTORY MANAGEMENT
# -----------------------------------------------------------------------------

@staff_member_required(login_url='store:login')
def product_list(request):
    """
    Product inventory list with category filtering, stock alerts, and quick actions.
    """
    products = (
        Product.objects.select_related('category')
        .prefetch_related('variants')
        .order_by('-created_at')
    )
    categories = Category.objects.all()

    category_slug = request.GET.get('category', '').strip()
    if category_slug:
        products = products.filter(category__slug=category_slug)

    search_query = request.GET.get('q', '').strip()
    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    return render(request, 'dashboard/product_list.html', {
        'products': products,
        'categories': categories,
        'active_category': category_slug,
        'search_query': search_query,
    })


@staff_member_required(login_url='store:login')
def product_create(request):
    """
    Add new product / jersey along with variant stocks for S, M, L, XL.
    """
    form = ProductForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        product = form.save()
        messages.success(request, f'Produk "{product.name}" berhasil ditambahkan!')
        return redirect('dashboard:product_list')

    return render(request, 'dashboard/product_form.html', {
        'form': form,
        'is_create': True,
    })


@staff_member_required(login_url='store:login')
def product_edit(request, product_id):
    """
    Edit existing product and update size variant stock.
    """
    product = get_object_or_404(Product.objects.prefetch_related('variants'), id=product_id)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Produk "{product.name}" berhasil diperbarui!')
        return redirect('dashboard:product_list')

    return render(request, 'dashboard/product_form.html', {
        'form': form,
        'product': product,
        'is_create': False,
    })


@require_POST
@staff_member_required(login_url='store:login')
def product_delete(request, product_id):
    """
    Delete a product from the database.
    """
    product = get_object_or_404(Product, id=product_id)
    product_name = product.name
    product.delete()
    messages.info(request, f'Produk "{product_name}" berhasil dihapus.')
    return redirect('dashboard:product_list')


# -----------------------------------------------------------------------------
# 5. CUSTOMER MANAGEMENT
# -----------------------------------------------------------------------------

@staff_member_required(login_url='store:login')
def customer_list(request):
    """
    Registered customer listing with order history statistics and total spent.
    """
    customers = (
        User.objects.filter(is_staff=False)
        .annotate(
            orders_count=Count('orders'),
            total_spent=Sum('orders__total')
        )
        .order_by('-date_joined')
    )

    search_query = request.GET.get('q', '').strip()
    if search_query:
        customers = customers.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query)
        )

    return render(request, 'dashboard/customer_list.html', {
        'customers': customers,
        'search_query': search_query,
    })


# -----------------------------------------------------------------------------
# 6. ARTICLE / CMS MANAGEMENT
# -----------------------------------------------------------------------------

@staff_member_required(login_url='store:login')
def article_list(request):
    """
    List all CMS articles / blog news.
    """
    articles = Article.objects.all().order_by('-created_at')
    return render(request, 'dashboard/article_list.html', {
        'articles': articles,
    })


@staff_member_required(login_url='store:login')
def article_create(request):
    """
    Create a new article or jersey announcement.
    """
    form = ArticleForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        article = form.save()
        messages.success(request, f'Artikel "{article.title}" berhasil dipublikasikan!')
        return redirect('dashboard:article_list')

    return render(request, 'dashboard/article_form.html', {
        'form': form,
        'is_create': True,
    })


@staff_member_required(login_url='store:login')
def article_edit(request, article_id):
    """
    Edit an existing article.
    """
    article = get_object_or_404(Article, id=article_id)
    form = ArticleForm(request.POST or None, request.FILES or None, instance=article)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'Artikel "{article.title}" berhasil diperbarui!')
        return redirect('dashboard:article_list')

    return render(request, 'dashboard/article_form.html', {
        'form': form,
        'article': article,
        'is_create': False,
    })


@require_POST
@staff_member_required(login_url='store:login')
def article_delete(request, article_id):
    """
    Delete an article.
    """
    article = get_object_or_404(Article, id=article_id)
    title = article.title
    article.delete()
    messages.info(request, f'Artikel "{title}" berhasil dihapus.')
    return redirect('dashboard:article_list')
