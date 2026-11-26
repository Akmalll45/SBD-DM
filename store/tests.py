import hashlib
import json
import tempfile
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import OrderStatusHistory
from dashboard.models import SiteSetting
from .models import (
    Cart,
    CartItem,
    Category,
    Order,
    OrderItem,
    Payment,
    PaymentStatusHistory,
    Product,
    ProductVariant,
)
from .payments import create_snap_transaction


@override_settings(
    BANK_TRANSFER_NAME='Test Bank',
    BANK_TRANSFER_ACCOUNT_NAME='Hendra Sport',
    BANK_TRANSFER_ACCOUNT_NUMBER='123456',
)
class CheckoutFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='buyer',
            email='buyer@example.test',
            password='test-password',
        )
        self.product, self.variant = self.make_product()
        self.cart = Cart.objects.create(user=self.user)
        self.client.login(username='buyer', password='test-password')

    def make_product(self, free_shipping=False):
        product_count = Product.objects.count()
        category = Category.objects.create(
            name=f'Jersey {product_count}',
            slug=f'jersey-{product_count}',
        )
        product = Product.objects.create(
            category=category,
            name=f'Jersey Test {product_count}',
            slug=f'jersey-test-{product_count}',
            description='Produk uji',
            base_price=Decimal('100000'),
            stock=3,
            free_shipping=free_shipping,
        )
        variant = ProductVariant.objects.create(product=product, size='M', stock=3)
        return product, variant

    def submit_shipping(self):
        response = self.client.post(reverse('store:checkout'), {
            'full_name': 'Pembeli Test',
            'phone': '081234567890',
            'city': 'Bandung',
            'address': 'Jl. Contoh No. 1',
            'courier': 'regular',
        })
        self.assertRedirects(response, reverse('store:checkout_confirm'))

    def test_cart_drawer_footer_updates_from_empty_to_one_item(self):
        product_url = reverse('store:product_detail', kwargs={'slug': self.product.slug})
        empty_cart_page = self.client.get(product_url)

        self.assertContains(empty_cart_page, 'id="cart-drawer-footer" hidden')

        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            variant=self.variant,
            quantity=1,
        )
        populated_cart_page = self.client.get(product_url)

        self.assertContains(populated_cart_page, 'id="cart-drawer-footer"')
        self.assertNotContains(populated_cart_page, 'id="cart-drawer-footer" hidden')
        self.assertContains(
            populated_cart_page,
            f'href="{reverse("store:checkout")}" class="button button--accent">Checkout</a>',
        )

    def test_confirmation_creates_order_with_shipping_and_print_snapshot(self):
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            variant=self.variant,
            quantity=2,
            has_sablon=True,
            custom_name='HENDRA',
            custom_number=10,
        )
        self.submit_shipping()
        confirmation = self.client.get(reverse('store:checkout_confirm'))
        self.assertEqual(confirmation.status_code, 200)

        response = self.client.post(reverse('store:checkout_confirm'), {
            'payment_method': Payment.Method.MANUAL_TRANSFER,
        })
        order = Order.objects.get(user=self.user)
        payment = Payment.objects.get(order=order)

        self.assertRedirects(
            response,
            reverse('store:payment_detail', kwargs={'order_id': order.pk}),
        )
        self.assertEqual(order.courier, 'Reguler (2–4 hari kerja)')
        self.assertEqual(order.shipping_cost, Decimal('18000'))
        self.assertEqual(order.total, Decimal('258000'))
        self.assertEqual(payment.amount, order.total)
        self.assertEqual(payment.method, Payment.Method.MANUAL_TRANSFER)
        self.assertEqual(order.items.get().sablon_fee, Decimal('20000'))
        self.assertEqual(self.variant.__class__.objects.get(pk=self.variant.pk).stock, 1)
        self.assertEqual(CartItem.objects.filter(cart=self.cart).count(), 0)
        self.assertIsNotNone(order.stock_reserved_at)
        self.assertEqual(
            list(payment.status_history.values_list('status', flat=True)),
            [Payment.Status.PENDING],
        )

    def test_all_free_shipping_items_are_charged_zero_shipping(self):
        product, variant = self.make_product(free_shipping=True)
        CartItem.objects.create(
            cart=self.cart,
            product=product,
            variant=variant,
            quantity=1,
        )
        self.submit_shipping()
        response = self.client.post(reverse('store:checkout_confirm'), {
            'payment_method': Payment.Method.MANUAL_TRANSFER,
        })
        order = Order.objects.get(user=self.user)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(order.shipping_cost, Decimal('0'))
        self.assertEqual(order.total, Decimal('100000'))


@override_settings(
    BANK_TRANSFER_NAME='Test Bank',
    BANK_TRANSFER_ACCOUNT_NAME='Hendra Sport',
    BANK_TRANSFER_ACCOUNT_NUMBER='123456',
)
class PaymentFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='payer',
            email='payer@example.test',
            password='test-password',
        )
        self.order = Order.objects.create(
            user=self.user,
            full_name='Pembeli Test',
            phone='081234567890',
            city='Bandung',
            address='Jl. Contoh No. 1',
            total=Decimal('100000'),
        )

    def create_payment(self, method, **kwargs):
        return Payment.objects.create(
            order=self.order,
            method=method,
            amount=self.order.total,
            **kwargs,
        )

    def test_manual_transfer_proof_is_reviewed_once_by_admin(self):
        temporary_media = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_media.cleanup)
        settings_override = override_settings(PAYMENT_PROOF_ROOT=temporary_media.name)
        settings_override.enable()
        self.addCleanup(settings_override.disable)

        payment = self.create_payment(Payment.Method.MANUAL_TRANSFER)
        self.client.login(username='payer', password='test-password')
        payment_page = self.client.get(
            reverse('store:payment_detail', kwargs={'order_id': self.order.pk})
        )
        self.assertEqual(payment_page.status_code, 200)
        invalid_proof = SimpleUploadedFile(
            'receipt.svg',
            b'<svg></svg>',
            content_type='image/svg+xml',
        )
        invalid_response = self.client.post(
            reverse('store:payment_detail', kwargs={'order_id': self.order.pk}),
            {'action': 'submit_proof', 'proof': invalid_proof},
        )
        self.assertEqual(invalid_response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

        proof = SimpleUploadedFile('receipt.pdf', b'%PDF-1.4\nproof', content_type='application/pdf')
        response = self.client.post(
            reverse('store:payment_detail', kwargs={'order_id': self.order.pk}),
            {'action': 'submit_proof', 'proof': proof},
        )

        payment.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(payment.status, Payment.Status.AWAITING_VERIFICATION)
        self.assertTrue(payment.proof.name)
        proof_response = self.client.get(
            reverse('store:payment_proof_file', kwargs={'order_id': self.order.pk})
        )
        self.assertEqual(proof_response['Content-Type'], 'application/pdf')
        self.assertEqual(b''.join(proof_response.streaming_content), b'%PDF-1.4\nproof')
        other_user = User.objects.create_user(username='other-payer', password='test-password')
        self.client.force_login(other_user)
        self.assertEqual(
            self.client.get(
                reverse('store:payment_proof_file', kwargs={'order_id': self.order.pk})
            ).status_code,
            404,
        )
        self.client.force_login(self.user)
        order_detail = self.client.get(
            reverse('accounts:order_detail', kwargs={'order_id': self.order.pk})
        )
        self.assertEqual(order_detail.status_code, 200)
        self.assertContains(order_detail, 'Riwayat pembayaran')
        self.assertContains(order_detail, 'Bukti transfer dikirim dan menunggu verifikasi admin.')

        staff = User.objects.create_user(username='staff', password='staff-password', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(
            self.client.get(
                reverse('dashboard:order_detail', kwargs={'order_id': self.order.pk})
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get(reverse('dashboard:payment_list')).status_code, 200)
        response = self.client.post(
            reverse('dashboard:review_payment', kwargs={'payment_id': payment.pk}),
            {'action': 'reject', 'rejection_note': 'Bukti tidak terbaca.'},
        )
        payment.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.rejection_note, 'Bukti tidak terbaca.')

        self.client.force_login(self.user)
        replacement_proof = SimpleUploadedFile(
            'receipt-again.pdf',
            b'%PDF-1.4\nreplacement',
            content_type='application/pdf',
        )
        self.client.post(
            reverse('store:payment_detail', kwargs={'order_id': self.order.pk}),
            {'action': 'submit_proof', 'proof': replacement_proof},
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.AWAITING_VERIFICATION)

        self.client.force_login(staff)
        response = self.client.post(
            reverse('dashboard:review_payment', kwargs={'payment_id': payment.pk}),
            {'action': 'approve'},
        )
        payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(payment.verified_by, staff)
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(
            list(payment.status_history.values_list('status', flat=True)),
            [
                Payment.Status.AWAITING_VERIFICATION,
                Payment.Status.FAILED,
                Payment.Status.AWAITING_VERIFICATION,
                Payment.Status.PAID,
            ],
        )

    @override_settings(MIDTRANS_SERVER_KEY='sandbox-test-key')
    def test_midtrans_notification_checks_signature_and_is_idempotent(self):
        payment = self.create_payment(
            Payment.Method.MIDTRANS,
            gateway_order_id='HS-101-test',
        )
        payload = {
            'order_id': payment.gateway_order_id,
            'status_code': '200',
            'gross_amount': '100000.00',
            'transaction_status': 'settlement',
            'transaction_id': 'txn-101',
        }
        signature = hashlib.sha512((
            f"{payload['order_id']}{payload['status_code']}"
            f"{payload['gross_amount']}sandbox-test-key"
        ).encode('utf-8')).hexdigest()
        payload['signature_key'] = signature
        url = reverse('store:midtrans_notification')

        invalid_payload = {**payload, 'signature_key': 'invalid'}
        invalid_response = self.client.post(
            url,
            data=json.dumps(invalid_payload),
            content_type='application/json',
        )
        self.assertEqual(invalid_response.status_code, 403)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

        mismatched_amount = {**payload, 'gross_amount': '99999.00'}
        mismatched_amount['signature_key'] = hashlib.sha512((
            f"{mismatched_amount['order_id']}{mismatched_amount['status_code']}"
            f"{mismatched_amount['gross_amount']}sandbox-test-key"
        ).encode('utf-8')).hexdigest()
        amount_response = self.client.post(
            url,
            data=json.dumps(mismatched_amount),
            content_type='application/json',
        )
        self.assertEqual(amount_response.status_code, 400)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
        )
        duplicate_response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
        )
        payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(duplicate_response.status_code, 200)
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(payment.gateway_transaction_id, 'txn-101')
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(
            PaymentStatusHistory.objects.filter(payment=payment, status=Payment.Status.PAID).count(),
            1,
        )
        self.assertEqual(
            OrderStatusHistory.objects.filter(
                order=self.order,
                status=Order.Status.PROCESSING,
            ).count(),
            1,
        )

    @override_settings(MIDTRANS_SERVER_KEY='sandbox-test-key')
    def test_expired_midtrans_payment_cancels_order_and_releases_stock_once(self):
        category = Category.objects.create(name='Stock', slug='stock')
        product = Product.objects.create(
            category=category,
            name='Stock Product',
            slug='stock-product',
            description='Stock test',
            base_price=Decimal('50000'),
            stock=1,
        )
        variant = ProductVariant.objects.create(product=product, size='M', stock=1)
        OrderItem.objects.create(
            order=self.order,
            product=product,
            variant=variant,
            product_name=product.name,
            size=variant.size,
            unit_price=Decimal('50000'),
            quantity=2,
        )
        self.order.stock_reserved_at = timezone.now()
        self.order.save(update_fields=['stock_reserved_at'])
        payment = self.create_payment(
            Payment.Method.MIDTRANS,
            gateway_order_id='HS-expired-test',
        )
        payload = {
            'order_id': payment.gateway_order_id,
            'status_code': '202',
            'gross_amount': '100000.00',
            'transaction_status': 'expire',
            'transaction_id': 'txn-expired',
        }
        payload['signature_key'] = hashlib.sha512((
            f"{payload['order_id']}{payload['status_code']}"
            f"{payload['gross_amount']}sandbox-test-key"
        ).encode('utf-8')).hexdigest()
        url = reverse('store:midtrans_notification')

        first_response = self.client.post(url, json.dumps(payload), content_type='application/json')
        second_response = self.client.post(url, json.dumps(payload), content_type='application/json')
        payment.refresh_from_db()
        self.order.refresh_from_db()
        variant.refresh_from_db()
        product.refresh_from_db()

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(payment.status, Payment.Status.EXPIRED)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertIsNotNone(self.order.stock_released_at)
        self.assertEqual(variant.stock, 3)
        self.assertEqual(product.stock, 3)

    @override_settings(
        MIDTRANS_SERVER_KEY='sandbox-test-key',
        MIDTRANS_CLIENT_KEY='sandbox-client-key',
    )
    @patch('store.payments.urlopen')
    def test_snap_transaction_reuses_saved_token(self, mock_urlopen):
        product = Product.objects.create(
            category=Category.objects.create(name='Gear', slug='gear'),
            name='Gear Test',
            slug='gear-test',
            description='Item invoice',
            base_price=Decimal('100000'),
        )
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name=product.name,
            size='M',
            unit_price=Decimal('100000'),
            quantity=1,
        )
        payment = self.create_payment(
            Payment.Method.MIDTRANS,
            gateway_order_id='HS-102-test',
        )
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = b'{"token":"snap-token","redirect_url":"https://app.sandbox.midtrans.com/snap/v2/vtweb/token"}'
        mock_urlopen.return_value = response

        token = create_snap_transaction(payment)
        repeated_token = create_snap_transaction(payment)
        request = mock_urlopen.call_args.args[0]
        request_payload = json.loads(request.data.decode('utf-8'))

        self.assertEqual(token, 'snap-token')
        self.assertEqual(repeated_token, 'snap-token')
        self.assertEqual(mock_urlopen.call_count, 1)
        self.assertEqual(request_payload['transaction_details']['gross_amount'], 100000)
        self.assertTrue(request.full_url.startswith('https://app.sandbox.midtrans.com/'))


class InvoiceTests(TestCase):
    def test_invoice_is_a_pdf_and_is_private_to_the_order_owner(self):
        owner = User.objects.create_user(username='invoice-owner', password='test-password')
        other_user = User.objects.create_user(username='invoice-other', password='test-password')
        category = Category.objects.create(name='Apparel', slug='apparel')
        product = Product.objects.create(
            category=category,
            name='Invoice Jersey',
            slug='invoice-jersey',
            description='Item invoice',
            base_price=Decimal('100000'),
        )
        order = Order.objects.create(
            user=owner,
            full_name='Pembeli Invoice',
            phone='081234567890',
            city='Jakarta',
            address='Jalan Invoice',
            total=Decimal('100000'),
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            size='L',
            unit_price=Decimal('100000'),
            quantity=1,
        )
        Payment.objects.create(
            order=order,
            method=Payment.Method.MANUAL_TRANSFER,
            amount=order.total,
        )

        self.client.force_login(owner)
        self.assertEqual(
            self.client.get(reverse('store:order_success', kwargs={'order_id': order.pk})).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('accounts:order_detail', kwargs={'order_id': order.pk})).status_code,
            200,
        )
        response = self.client.get(reverse('store:invoice_pdf', kwargs={'order_id': order.pk}))
        content = b''.join(response.streaming_content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(content.startswith(b'%PDF-'))

        self.client.force_login(other_user)
        self.assertEqual(
            self.client.get(reverse('store:invoice_pdf', kwargs={'order_id': order.pk})).status_code,
            404,
        )


class AboutPageTests(TestCase):
    def test_about_page_has_sections_and_does_not_publish_default_contacts(self):
        SiteSetting.objects.create()

        response = self.client.get(reverse('store:about'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Profil Hendra Sport')
        self.assertContains(response, 'Visi &amp; Misi')
        self.assertContains(response, 'Layanan Custom Jersey')
        self.assertContains(response, 'Mengapa Hendra Sport?')
        self.assertContains(response, 'Hubungi Kami')
        self.assertContains(response, 'Menyediakan produk olahraga yang berkualitas.')
        self.assertContains(response, 'href="https://www.instagram.com/hendrasport_andalas/"')
        self.assertContains(response, '@hendrasport_andalas')
        self.assertContains(response, 'Informasi kontak belum tersedia')
        self.assertNotContains(response, 'support@hendrasport.com')
        self.assertNotContains(response, '6281234567890')

    def test_about_page_links_to_configured_email_and_whatsapp(self):
        SiteSetting.objects.create(
            contact_email='halo@hendra.test',
            contact_phone='+62 812-5555-4444',
        )

        response = self.client.get(reverse('store:about'))

        self.assertContains(response, 'href="mailto:halo@hendra.test"')
        self.assertContains(response, 'href="https://wa.me/6281255554444"')


class ProductTypeDisplayTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Sports Gear', slug='sports-gear')

    def create_product(self, product_type, name, slug):
        return Product.objects.create(
            category=self.category,
            product_type=product_type,
            name=name,
            slug=slug,
            description='Deskripsi produk yang dapat diatur dari panel admin.',
            base_price=Decimal('150000'),
            stock=10,
        )

    def test_equipment_detail_hides_jersey_customization_and_uses_default_variant(self):
        product = self.create_product(
            Product.ProductType.EQUIPMENT,
            'Bola Latihan',
            'bola-latihan-detail',
        )
        variant = ProductVariant.objects.create(product=product, size='ALL', stock=10)

        response = self.client.get(reverse('store:product_detail', kwargs={'slug': product.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, product.description)
        self.assertContains(response, f'value="{variant.id}"')
        self.assertContains(response, 'Harga Produk:')
        self.assertNotContains(response, 'Harga Jersey:')
        self.assertNotContains(response, 'HEAT.RDY')
        self.assertNotContains(response, 'Polyflex High-Grade')
        self.assertNotContains(response, 'Panduan Ukuran (S, M, L, XL)')
        self.assertNotContains(response, 'Layanan Sablon Custom')
        self.assertNotContains(response, 'id="sablon-checkbox"')
        self.assertNotContains(response, 'Ukuran Jersey:')
        self.assertNotContains(response, 'data-size="ALL"')

    def test_jersey_detail_keeps_size_and_sablon_controls(self):
        product = self.create_product(Product.ProductType.JERSEY, 'Jersey Tes', 'jersey-detail')
        ProductVariant.objects.create(product=product, size='M', stock=10)

        response = self.client.get(reverse('store:product_detail', kwargs={'slug': product.slug}))

        self.assertContains(response, 'Harga Jersey:')
        self.assertContains(response, 'id="sablon-checkbox"')
        self.assertContains(response, 'Pilih Ukuran Jersey:')

    def test_footwear_detail_keeps_shoe_sizes_without_sablon(self):
        product = self.create_product(
            Product.ProductType.FOOTWEAR,
            'Sepatu Latihan',
            'sepatu-latihan-detail',
        )
        ProductVariant.objects.create(product=product, size='39', stock=4)

        response = self.client.get(reverse('store:product_detail', kwargs={'slug': product.slug}))

        self.assertContains(response, 'Pilih Ukuran Sepatu:')
        self.assertContains(response, 'data-size="39"')
        self.assertNotContains(response, 'id="sablon-checkbox"')
