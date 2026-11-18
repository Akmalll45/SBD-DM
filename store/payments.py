import base64
import hashlib
import hmac
import json
import logging
import secrets
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from .models import Order, Payment, PaymentStatusHistory, Product, ProductVariant

logger = logging.getLogger(__name__)

MIDTRANS_SNAP_URL = 'https://app.sandbox.midtrans.com/snap/v1/transactions'


class PaymentGatewayError(Exception):
    pass


def new_gateway_order_id(order_id):
    return f'HS-{order_id}-{secrets.token_hex(6)}'


def create_snap_transaction(payment):
    if not settings.MIDTRANS_SERVER_KEY or not settings.MIDTRANS_CLIENT_KEY:
        raise PaymentGatewayError('Pembayaran Midtrans Sandbox belum dikonfigurasi.')

    with transaction.atomic():
        locked_payment = (
            Payment.objects.select_for_update()
            .select_related('order', 'order__user')
            .get(pk=payment.pk)
        )
        if locked_payment.method != Payment.Method.MIDTRANS:
            raise PaymentGatewayError('Metode pembayaran pesanan ini bukan Midtrans.')
        if locked_payment.status != Payment.Status.PENDING:
            raise PaymentGatewayError('Status pembayaran tidak lagi menunggu pembayaran.')
        if locked_payment.snap_token:
            return locked_payment.snap_token

        order = locked_payment.order
        item_details = [
            {
                'id': f'product-{item.product_id}',
                'price': int(item.unit_price),
                'quantity': item.quantity,
                'name': item.product_name[:50],
            }
            for item in order.items.all()
        ]
        if order.shipping_cost:
            item_details.append({
                'id': 'shipping',
                'price': int(order.shipping_cost),
                'quantity': 1,
                'name': f'Ongkos kirim - {order.courier}'[:50],
            })

        name_parts = order.full_name.split(maxsplit=1)
        customer_details = {
            'first_name': name_parts[0][:50],
            'last_name': name_parts[1][:50] if len(name_parts) > 1 else '',
            'phone': order.phone,
        }
        if order.user.email:
            customer_details['email'] = order.user.email

        payload = {
            'transaction_details': {
                'order_id': locked_payment.gateway_order_id,
                'gross_amount': int(locked_payment.amount),
            },
            'item_details': item_details,
            'customer_details': customer_details,
            'expiry': {
                'start_time': timezone.localtime().strftime('%Y-%m-%d %H:%M:%S %z'),
                'unit': 'hour',
                'duration': 24,
            },
        }
        encoded_credentials = base64.b64encode(
            f'{settings.MIDTRANS_SERVER_KEY}:'.encode('utf-8')
        ).decode('ascii')
        request = Request(
            MIDTRANS_SNAP_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'Authorization': f'Basic {encoded_credentials}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            method='POST',
        )

        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            logger.warning('Midtrans Snap request failed with HTTP %s.', exc.code)
            raise PaymentGatewayError('Midtrans Sandbox tidak dapat membuat tagihan saat ini.') from exc
        except (URLError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            logger.warning('Midtrans Snap request could not be completed: %s', exc)
            raise PaymentGatewayError('Midtrans Sandbox tidak dapat dijangkau saat ini.') from exc

        token = result.get('token')
        redirect_url = result.get('redirect_url')
        if not token or not redirect_url:
            logger.error('Midtrans Snap response did not contain a token and redirect URL.')
            raise PaymentGatewayError('Respons pembayaran Midtrans tidak lengkap.')

        locked_payment.snap_token = token
        locked_payment.snap_redirect_url = redirect_url
        locked_payment.save(update_fields=['snap_token', 'snap_redirect_url', 'updated_at'])
        return token


def verify_midtrans_signature(payload, server_key=None):
    server_key = server_key if server_key is not None else settings.MIDTRANS_SERVER_KEY
    signature = payload.get('signature_key', '')
    order_id = payload.get('order_id', '')
    status_code = payload.get('status_code', '')
    gross_amount = payload.get('gross_amount', '')
    if not all((server_key, signature, order_id, status_code, gross_amount)):
        return False
    digest = hashlib.sha512(
        f'{order_id}{status_code}{gross_amount}{server_key}'.encode('utf-8')
    ).hexdigest()
    return hmac.compare_digest(digest, signature)


def mark_payment_paid(payment, verified_by=None):
    if payment.status == Payment.Status.PAID:
        return False

    now = timezone.now()
    payment.status = Payment.Status.PAID
    payment.paid_at = payment.paid_at or now
    update_fields = ['status', 'paid_at', 'updated_at']
    if payment.method == Payment.Method.MANUAL_TRANSFER:
        payment.verified_by = verified_by
        payment.verified_at = now
        update_fields.extend(['verified_by', 'verified_at'])
    payment.save(update_fields=update_fields)
    record_payment_status(
        payment,
        'Pembayaran berhasil diverifikasi.',
        actor=verified_by,
    )

    order = Order.objects.select_for_update().get(pk=payment.order_id)
    if order.status == Order.Status.PENDING:
        order.status = Order.Status.PROCESSING
        order.save(update_fields=['status'])
    return True


def record_payment_status(payment, note, actor=None):
    return PaymentStatusHistory.objects.create(
        payment=payment,
        status=payment.status,
        note=note[:255],
        actor=actor,
    )


def release_order_stock(order):
    locked_order = Order.objects.select_for_update().get(pk=order.pk)
    if not locked_order.stock_reserved_at or locked_order.stock_released_at:
        return False

    quantities = list(
        locked_order.items.exclude(variant__isnull=True)
        .values('variant_id', 'variant__product_id')
        .annotate(quantity=Sum('quantity'))
        .order_by('variant_id')
    )
    variant_ids = [entry['variant_id'] for entry in quantities]
    product_ids = sorted({entry['variant__product_id'] for entry in quantities})
    list(Product.objects.select_for_update().filter(pk__in=product_ids).order_by('pk'))
    list(ProductVariant.objects.select_for_update().filter(pk__in=variant_ids).order_by('pk'))

    for entry in quantities:
        ProductVariant.objects.filter(pk=entry['variant_id']).update(
            stock=F('stock') + entry['quantity']
        )
        Product.objects.filter(pk=entry['variant__product_id']).update(
            stock=F('stock') + entry['quantity']
        )

    locked_order.stock_released_at = timezone.now()
    locked_order.save(update_fields=['stock_released_at'])
    return True
