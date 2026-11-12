from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from store.models import Order

from .forms import IndonesianPasswordChangeForm, ProfileForm
from .models import OrderStatusHistory, Profile


def _profile_for(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


@login_required
def account_dashboard(request):
    profile = _profile_for(request.user)
    orders = Order.objects.filter(user=request.user)
    recent_orders = (
        orders.annotate(item_count=Count('items'))
        .order_by('-created_at')[:3]
    )
    return render(request, 'accounts/dashboard.html', {
        'profile': profile,
        'pending_count': orders.filter(status=Order.Status.PENDING).count(),
        'processing_count': orders.filter(
            status__in=[Order.Status.PAID, Order.Status.PROCESSING]
        ).count(),
        'shipped_count': orders.filter(status=Order.Status.SHIPPED).count(),
        'completed_count': orders.filter(status=Order.Status.COMPLETED).count(),
        'recent_orders': recent_orders,
    })


@login_required
def profile_edit(request):
    profile = _profile_for(request.user)
    form = ProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=request.user,
        profile=profile,
    )
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profil berhasil diperbarui.')
        return redirect('accounts:profile')
    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
        'avatar_initial': (request.user.first_name or request.user.username or 'P')[0].upper(),
    })


@method_decorator(login_required, name='dispatch')
class AccountPasswordChangeView(PasswordChangeView):
    form_class = IndonesianPasswordChangeForm
    template_name = 'accounts/password.html'
    success_url = reverse_lazy('accounts:password')

    def form_valid(self, form):
        messages.success(self.request, 'Kata sandi berhasil diubah.')
        return super().form_valid(form)


@login_required
def order_list(request):
    orders = (
        Order.objects.filter(user=request.user)
        .annotate(item_count=Count('items'))
        .order_by('-created_at')
    )
    selected_status = request.GET.get('status', '')
    if selected_status in Order.Status.values:
        orders = orders.filter(status=selected_status)
    paginator = Paginator(orders, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/orders.html', {
        'page_obj': page_obj,
        'selected_status': selected_status,
        'status_choices': Order.Status.choices,
    })


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.filter(user=request.user)
        .select_related('user')
        .prefetch_related('items__product', 'items__variant', 'status_history'),
        pk=order_id,
    )
    items = list(order.items.all())
    print_fee = Decimal(str(settings.SABLON_FEE))
    print_total = sum(
        (print_fee * item.quantity for item in items if item.has_sablon),
        Decimal('0'),
    )
    history = list(order.status_history.all())
    steps = [
        {'status': Order.Status.PENDING, 'label': 'Menunggu Bayar'},
        {'status': Order.Status.PROCESSING, 'label': 'Diproses'},
        {'status': Order.Status.SHIPPED, 'label': 'Dikirim'},
        {'status': Order.Status.COMPLETED, 'label': 'Selesai'},
    ]
    current_step = {
        Order.Status.PENDING: 0,
        Order.Status.PAID: 1,
        Order.Status.PROCESSING: 1,
        Order.Status.SHIPPED: 2,
        Order.Status.COMPLETED: 3,
    }.get(order.status, -1)
    return render(request, 'accounts/order_detail.html', {
        'order': order,
        'items': items,
        'history': history,
        'steps': steps,
        'current_step': current_step,
        'items_subtotal': order.total - print_total,
        'print_total': print_total,
        'print_fee': print_fee,
        'fallback_status': Order.Status.PENDING,
    })


@login_required
@require_POST
def cancel_order(request, order_id):
    with transaction.atomic():
        order = get_object_or_404(
            Order.objects.select_for_update().filter(user=request.user),
            pk=order_id,
        )
        if order.status != Order.Status.PENDING:
            messages.error(request, 'Pesanan hanya dapat dibatalkan saat menunggu pembayaran.')
        else:
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status'])
            messages.success(request, f'Pesanan #{order.pk} berhasil dibatalkan.')
    return redirect('accounts:order_detail', order_id=order_id)
