import base64
import secrets
import time
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.contrib.sessions.models import Session
from django.core import signing
from django.core.exceptions import SuspiciousOperation
from django.core.mail import send_mail
from django.contrib.auth.hashers import check_password, make_password
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST

from store.models import Order, Payment
from store.payments import release_order_stock, sync_midtrans_payment

from .forms import AddressForm, IndonesianPasswordChangeForm, ProfileForm, VerificationCodeForm
from .models import Address, LoginActivity, OrderStatusHistory, Profile
from .security import matching_totp_counter, new_totp_secret, session_key_hash


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
        email_changed = form.cleaned_data['email'] != request.user.email
        form.save()
        if email_changed and request.user.email:
            _send_email_verification(request)
        messages.success(request, 'Profil berhasil diperbarui.')
        return redirect('accounts:profile')
    return render(request, 'accounts/profile.html', {
        'form': form,
        'profile': profile,
        'addresses': Address.objects.filter(user=request.user),
        'verification_form': VerificationCodeForm(),
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
    # Auto-sync any pending Midtrans payments for this user so status is always fresh
    pending_user_midtrans = list(Payment.objects.filter(
        order__user=request.user,
        method=Payment.Method.MIDTRANS,
        status=Payment.Status.PENDING,
    ).select_related('order'))
    for p in pending_user_midtrans:
        sync_midtrans_payment(p)

    orders = (
        Order.objects.filter(user=request.user)
        .select_related('payment')
        .annotate(item_count=Count('items'))
        .order_by('-created_at')
    )
    selected_status = request.GET.get('status', '')
    if selected_status == 'paid':
        # "Sudah Dibayar" = payment lunas, tapi order bisa sudah lanjut ke processing/shipped/completed
        orders = orders.filter(payment__status=Payment.Status.PAID)
    elif selected_status in Order.Status.values:
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
        .select_related('user', 'payment')
        .prefetch_related(
            'items__product',
            'items__variant',
            'status_history',
            'payment__status_history__actor',
        ),
        pk=order_id,
    )
    payment = getattr(order, 'payment', None)
    if payment and payment.method == Payment.Method.MIDTRANS and payment.status != Payment.Status.PAID:
        sync_midtrans_payment(payment)
        order.refresh_from_db()
        payment = getattr(order, 'payment', None)

    items = list(order.items.all())
    print_total = sum((item.sablon_total for item in items), Decimal('0'))
    items_subtotal = sum((item.line_total for item in items), Decimal('0')) - print_total
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
        'payment': payment,
        'history': history,
        'payment_history': list(payment.status_history.all()) if payment else [],
        'steps': steps,
        'current_step': current_step,
        'items_subtotal': items_subtotal,
        'print_total': print_total,
        'fallback_status': Order.Status.PENDING,
    })


@login_required
@require_POST
def cancel_order(request, order_id):
    with transaction.atomic():
        payment = (
            Payment.objects.select_for_update()
            .filter(order__user=request.user, order_id=order_id)
            .first()
        )
        order = get_object_or_404(
            Order.objects.select_for_update().filter(user=request.user),
            pk=order_id,
        )
        payment_active = payment and (
            payment.status in (
                Payment.Status.PAID,
                Payment.Status.AWAITING_VERIFICATION,
            )
            or (
                payment.method == Payment.Method.MIDTRANS
                and payment.status == Payment.Status.PENDING
                and bool(payment.snap_token)
            )
        )
        if order.status != Order.Status.PENDING or payment_active:
            messages.error(
                request,
                'Pesanan tidak dapat dibatalkan saat pembayaran sudah lunas, '
                'menunggu verifikasi, atau memiliki tagihan Midtrans aktif.',
            )
        else:
            order.status = Order.Status.CANCELLED
            order.save(update_fields=['status'])
            release_order_stock(order)
            messages.success(request, f'Pesanan #{order.pk} berhasil dibatalkan.')
    return redirect('accounts:order_detail', order_id=order_id)


def _send_email_verification(request):
    if not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL:
        messages.error(
            request,
            'Verifikasi email belum dapat dikirim. Admin perlu mengatur EMAIL_HOST dan DEFAULT_FROM_EMAIL.',
        )
        return False

    token = signing.dumps(
        {'user_id': request.user.pk, 'email': request.user.email},
        salt='accounts.email-verification',
    )
    verification_url = request.build_absolute_uri(
        reverse('accounts:verify_email', kwargs={'token': token})
    )
    try:
        sent = send_mail(
            'Verifikasi email Hendra Sport',
            f'Klik tautan berikut untuk memverifikasi email Anda: {verification_url}',
            settings.DEFAULT_FROM_EMAIL,
            [request.user.email],
            fail_silently=False,
        )
    except (OSError, RuntimeError) as error:
        messages.error(request, f'Email verifikasi gagal dikirim: {error}')
        return False

    if sent != 1:
        messages.error(request, 'Email verifikasi tidak terkirim. Periksa konfigurasi SMTP.')
        return False
    messages.info(request, 'Tautan verifikasi telah dikirim ke alamat email Anda.')
    return True


@login_required
@require_POST
def send_email_verification(request):
    profile = _profile_for(request.user)
    if not request.user.email:
        messages.error(request, 'Tambahkan alamat email terlebih dahulu.')
    elif profile.email_verified:
        messages.info(request, 'Alamat email ini sudah terverifikasi.')
    else:
        _send_email_verification(request)
    return redirect('accounts:profile')


@login_required
def verify_email(request, token):
    try:
        payload = signing.loads(
            token,
            salt='accounts.email-verification',
            max_age=settings.EMAIL_VERIFICATION_MAX_AGE,
        )
    except signing.SignatureExpired:
        messages.error(request, 'Tautan verifikasi email sudah kedaluwarsa. Minta tautan baru.')
        return redirect('accounts:profile')
    except signing.BadSignature:
        messages.error(request, 'Tautan verifikasi email tidak valid.')
        return redirect('accounts:profile')

    if payload.get('user_id') != request.user.pk or payload.get('email') != request.user.email:
        raise SuspiciousOperation('Email verification token does not match the current account.')
    profile = _profile_for(request.user)
    profile.email_verified = True
    profile.save(update_fields=['email_verified'])
    messages.success(request, 'Alamat email berhasil diverifikasi.')
    return redirect('accounts:profile')


@login_required
@require_POST
def send_phone_verification(request):
    profile = _profile_for(request.user)
    if not profile.phone:
        messages.error(request, 'Tambahkan nomor telepon terlebih dahulu.')
        return redirect('accounts:profile')
    if not all((
        settings.TWILIO_ACCOUNT_SID,
        settings.TWILIO_AUTH_TOKEN,
        settings.TWILIO_FROM_NUMBER,
    )):
        messages.error(
            request,
            'Verifikasi nomor belum tersedia. Admin perlu mengatur TWILIO_ACCOUNT_SID, '
            'TWILIO_AUTH_TOKEN, dan TWILIO_FROM_NUMBER.',
        )
        return redirect('accounts:profile')
    if profile.phone_otp_sent_at and timezone.now() - profile.phone_otp_sent_at < timedelta(seconds=60):
        messages.error(request, 'Tunggu satu menit sebelum meminta kode verifikasi baru.')
        return redirect('accounts:profile')

    code = f'{secrets.randbelow(1_000_000):06d}'
    message_data = urlencode({
        'To': profile.phone,
        'From': settings.TWILIO_FROM_NUMBER,
        'Body': f'Kode verifikasi Hendra Sport Anda: {code}. Kode berlaku 10 menit.',
    }).encode('utf-8')
    twilio_url = (
        'https://api.twilio.com/2010-04-01/Accounts/'
        f'{settings.TWILIO_ACCOUNT_SID}/Messages.json'
    )
    auth_value = base64.b64encode(
        f'{settings.TWILIO_ACCOUNT_SID}:{settings.TWILIO_AUTH_TOKEN}'.encode('utf-8')
    ).decode('ascii')
    twilio_request = Request(twilio_url, data=message_data, method='POST')
    twilio_request.add_header('Authorization', f'Basic {auth_value}')
    twilio_request.add_header('Content-Type', 'application/x-www-form-urlencoded')
    try:
        with urlopen(twilio_request, timeout=10) as response:
            if response.status not in (200, 201):
                messages.error(request, f'Twilio menolak pengiriman kode (HTTP {response.status}).')
                return redirect('accounts:profile')
    except HTTPError as error:
        messages.error(request, f'Twilio gagal mengirim kode (HTTP {error.code}). Periksa konfigurasi akun.')
        return redirect('accounts:profile')
    except (TimeoutError, URLError):
        messages.error(request, 'Layanan SMS tidak dapat dijangkau. Coba kembali beberapa saat lagi.')
        return redirect('accounts:profile')

    profile.phone_otp_hash = make_password(code)
    profile.phone_otp_sent_at = timezone.now()
    profile.phone_otp_attempts = 0
    profile.phone_verified = False
    profile.save(update_fields=[
        'phone_otp_hash',
        'phone_otp_sent_at',
        'phone_otp_attempts',
        'phone_verified',
    ])
    messages.success(request, 'Kode verifikasi telah dikirim melalui SMS.')
    return redirect('accounts:profile')


@login_required
@require_POST
def verify_phone(request):
    form = VerificationCodeForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Masukkan kode SMS 6 digit yang valid.')
        return redirect('accounts:profile')
    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(user=request.user)
        if not profile.phone_otp_hash or not profile.phone_otp_sent_at:
            messages.error(request, 'Minta kode verifikasi terlebih dahulu.')
            return redirect('accounts:profile')
        if timezone.now() - profile.phone_otp_sent_at > timedelta(seconds=settings.PHONE_VERIFICATION_MAX_AGE):
            profile.phone_otp_hash = ''
            profile.phone_otp_sent_at = None
            profile.phone_otp_attempts = 0
            profile.save(update_fields=['phone_otp_hash', 'phone_otp_sent_at', 'phone_otp_attempts'])
            messages.error(request, 'Kode SMS sudah kedaluwarsa. Minta kode baru.')
            return redirect('accounts:profile')
        if profile.phone_otp_attempts >= 5:
            messages.error(request, 'Batas percobaan kode tercapai. Minta kode baru.')
            return redirect('accounts:profile')

        profile.phone_otp_attempts += 1
        if check_password(form.cleaned_data['code'], profile.phone_otp_hash):
            profile.phone_verified = True
            profile.phone_otp_hash = ''
            profile.phone_otp_sent_at = None
            profile.phone_otp_attempts = 0
            profile.save(update_fields=[
                'phone_verified',
                'phone_otp_hash',
                'phone_otp_sent_at',
                'phone_otp_attempts',
            ])
            messages.success(request, 'Nomor telepon berhasil diverifikasi.')
        else:
            profile.save(update_fields=['phone_otp_attempts'])
            messages.error(request, 'Kode verifikasi tidak sesuai.')
    return redirect('accounts:profile')


@login_required
def address_edit(request, address_id=None):
    address = None
    if address_id is not None:
        address = get_object_or_404(Address, pk=address_id, user=request.user)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            saved_address = form.save(commit=False)
            saved_address.user = request.user
            has_other_primary = Address.objects.filter(
                user=request.user,
                is_primary=True,
            ).exclude(pk=saved_address.pk).exists()
            if saved_address.is_primary or not has_other_primary:
                Address.objects.filter(user=request.user).update(is_primary=False)
                saved_address.is_primary = True
            saved_address.save()
        messages.success(request, 'Alamat berhasil disimpan.')
        return redirect('accounts:profile')
    return render(request, 'accounts/address_form.html', {'form': form, 'address': address})


@login_required
@require_POST
def address_delete(request, address_id):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        address = get_object_or_404(
            Address.objects.select_for_update().filter(user=request.user),
            pk=address_id,
        )
        was_primary = address.is_primary
        address.delete()
        if was_primary:
            next_address = Address.objects.filter(user=request.user).order_by('created_at', 'pk').first()
            if next_address:
                next_address.is_primary = True
                next_address.save(update_fields=['is_primary'])
    messages.success(request, 'Alamat berhasil dihapus.')
    return redirect('accounts:profile')


@login_required
@require_POST
def address_set_primary(request, address_id):
    with transaction.atomic():
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        address = get_object_or_404(
            Address.objects.select_for_update().filter(user=request.user),
            pk=address_id,
        )
        Address.objects.filter(user=request.user).update(is_primary=False)
        address.is_primary = True
        address.save(update_fields=['is_primary'])
    messages.success(request, 'Alamat utama berhasil diperbarui.')
    return redirect('accounts:profile')


@login_required
def account_security(request):
    profile = _profile_for(request.user)
    secret = profile.totp_pending_secret
    issuer = 'Hendra Sport'
    label = f'{issuer}:{request.user.email or request.user.username}'
    totp_uri = ''
    if secret:
        from urllib.parse import quote

        totp_uri = (
            f'otpauth://totp/{quote(label)}?secret={secret}'
            f'&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30'
        )
    activities = LoginActivity.objects.filter(user=request.user)[:10]
    return render(request, 'accounts/security.html', {
        'profile': profile,
        'activities': activities,
        'totp_uri': totp_uri,
        'current_session_hash': (
            session_key_hash(request.session.session_key, settings.SECRET_KEY)
            if request.session.session_key else ''
        ),
    })


@login_required
@require_POST
def start_totp_setup(request):
    profile = _profile_for(request.user)
    if profile.totp_enabled:
        messages.info(request, 'Autentikasi dua langkah sudah aktif.')
    else:
        profile.totp_pending_secret = new_totp_secret()
        profile.totp_attempts = 0
        profile.totp_lockout_until = None
        profile.save(update_fields=['totp_pending_secret', 'totp_attempts', 'totp_lockout_until'])
        messages.info(request, 'Tambahkan kunci ini ke aplikasi authenticator, lalu masukkan kode untuk mengaktifkan.')
    return redirect('accounts:security')


@login_required
@require_POST
@transaction.atomic
def confirm_totp_setup(request):
    profile = Profile.objects.select_for_update().get(user=request.user)
    form = VerificationCodeForm(request.POST)
    if not profile.totp_pending_secret or not form.is_valid():
        messages.error(request, 'Mulai pengaturan authenticator dan masukkan kode 6 digit yang valid.')
        return redirect('accounts:security')
    if profile.totp_lockout_until and profile.totp_lockout_until > timezone.now():
        messages.error(request, 'Percobaan dibatasi sementara. Coba lagi setelah masa tunggu berakhir.')
        return redirect('accounts:security')
    counter = matching_totp_counter(profile.totp_pending_secret, form.cleaned_data['code'])
    if counter is None:
        profile.totp_attempts += 1
        if profile.totp_attempts >= 5:
            profile.totp_attempts = 0
            profile.totp_lockout_until = timezone.now() + timedelta(minutes=10)
        profile.save(update_fields=['totp_attempts', 'totp_lockout_until'])
        messages.error(request, 'Kode authenticator tidak sesuai.')
        return redirect('accounts:security')

    profile.totp_secret = profile.totp_pending_secret
    profile.totp_pending_secret = ''
    profile.totp_enabled = True
    profile.totp_last_counter = counter
    profile.totp_attempts = 0
    profile.totp_lockout_until = None
    profile.save(update_fields=[
        'totp_secret',
        'totp_pending_secret',
        'totp_enabled',
        'totp_last_counter',
        'totp_attempts',
        'totp_lockout_until',
    ])
    messages.success(request, 'Autentikasi dua langkah berhasil diaktifkan.')
    return redirect('accounts:security')


@login_required
@require_POST
@transaction.atomic
def disable_totp(request):
    profile = Profile.objects.select_for_update().get(user=request.user)
    form = VerificationCodeForm(request.POST)
    if not profile.totp_enabled or not form.is_valid():
        messages.error(request, 'Masukkan kode authenticator yang valid untuk menonaktifkan.')
        return redirect('accounts:security')
    if profile.totp_lockout_until and profile.totp_lockout_until > timezone.now():
        messages.error(request, 'Percobaan dibatasi sementara. Coba lagi setelah masa tunggu berakhir.')
        return redirect('accounts:security')
    counter = matching_totp_counter(profile.totp_secret, form.cleaned_data['code'])
    if counter is None or counter <= profile.totp_last_counter:
        profile.totp_attempts += 1
        if profile.totp_attempts >= 5:
            profile.totp_attempts = 0
            profile.totp_lockout_until = timezone.now() + timedelta(minutes=10)
        profile.save(update_fields=['totp_attempts', 'totp_lockout_until'])
        messages.error(request, 'Kode authenticator tidak valid atau sudah pernah digunakan.')
        return redirect('accounts:security')
    profile.totp_enabled = False
    profile.totp_secret = ''
    profile.totp_pending_secret = ''
    profile.totp_last_counter = -1
    profile.totp_attempts = 0
    profile.totp_lockout_until = None
    profile.save(update_fields=[
        'totp_enabled',
        'totp_secret',
        'totp_pending_secret',
        'totp_last_counter',
        'totp_attempts',
        'totp_lockout_until',
    ])
    messages.success(request, 'Autentikasi dua langkah berhasil dinonaktifkan.')
    return redirect('accounts:security')


@require_POST
def _verify_totp_login(request, user_id):
    User = get_user_model()
    user = get_object_or_404(User, pk=user_id, is_active=True)
    form = VerificationCodeForm(request.POST)
    with transaction.atomic():
        profile = Profile.objects.select_for_update().get(user=user)
        if form.is_valid() and profile.totp_enabled:
            if profile.totp_lockout_until and profile.totp_lockout_until > timezone.now():
                messages.error(request, 'Percobaan autentikasi dibatasi sementara. Coba lagi nanti.')
                return render(request, 'store/totp_challenge.html', {'form': form})
            counter = matching_totp_counter(profile.totp_secret, form.cleaned_data['code'])
            if counter is not None and counter > profile.totp_last_counter:
                profile.totp_last_counter = counter
                profile.totp_attempts = 0
                profile.totp_lockout_until = None
                profile.save(update_fields=['totp_last_counter', 'totp_attempts', 'totp_lockout_until'])
                next_url = request.session.pop('pending_totp_next', reverse_lazy('store:home'))
                request.session.pop('pending_totp_user_id', None)
                request.session.pop('pending_totp_created', None)
                login(request, user)
                messages.success(request, f'Selamat datang kembali, {user.username}!')
                return redirect(next_url)

        if profile.totp_enabled:
            profile.totp_attempts += 1
            if profile.totp_attempts >= 5:
                profile.totp_attempts = 0
                profile.totp_lockout_until = timezone.now() + timedelta(minutes=10)
            profile.save(update_fields=['totp_attempts', 'totp_lockout_until'])
        messages.error(request, 'Kode authenticator tidak sesuai.')
        return render(request, 'store/totp_challenge.html', {'form': form})


def totp_login_page(request):
    if request.user.is_authenticated:
        return redirect('store:home')
    user_id = request.session.get('pending_totp_user_id')
    if not user_id:
        return redirect('store:login')
    if time.time() - request.session.get('pending_totp_created', 0) > 300:
        request.session.pop('pending_totp_user_id', None)
        request.session.pop('pending_totp_next', None)
        request.session.pop('pending_totp_created', None)
        messages.error(request, 'Sesi verifikasi masuk berakhir. Silakan masuk kembali.')
        return redirect('store:login')
    form = VerificationCodeForm(request.POST or None)
    if request.method == 'POST':
        return _verify_totp_login(request, user_id)
    return render(request, 'store/totp_challenge.html', {'form': form})


@login_required
@require_POST
def logout_other_devices(request):
    if settings.SESSION_ENGINE != 'django.contrib.sessions.backends.db':
        messages.error(request, 'Keluar dari perangkat lain belum didukung oleh backend sesi saat ini.')
        return redirect('accounts:security')
    current_key = request.session.session_key
    logout_count = 0
    for session in Session.objects.iterator():
        if session.session_key == current_key:
            continue
        if str(session.get_decoded().get('_auth_user_id', '')) == str(request.user.pk):
            session.delete()
            logout_count += 1
    messages.success(request, f'{logout_count} sesi perangkat lain berhasil dikeluarkan.')
    return redirect('accounts:security')
