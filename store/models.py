from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models

from .storage import PrivatePaymentProofStorage, SablonRosterStorage


class Category(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    class ProductType(models.TextChoices):
        JERSEY = 'jersey', 'Jersey / Pakaian Olahraga'
        FOOTWEAR = 'footwear', 'Sepatu & Footwear'
        EQUIPMENT = 'equipment', 'Peralatan / Bola / Aksesoris (All Size)'

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
    )
    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        default=ProductType.JERSEY,
        help_text='Jenis produk untuk menentukan satuan ukuran dan kustomisasi sablon'
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    description = models.TextField()
    base_price = models.DecimalField(max_digits=12, decimal_places=0)
    discount_price = models.DecimalField(max_digits=12, decimal_places=0, null=True, blank=True)
    image = models.ImageField(upload_to='products/', blank=True)
    front_image = models.ImageField(upload_to='products/', blank=True, null=True)
    back_image = models.ImageField(upload_to='products/', blank=True, null=True)
    material_spec = models.TextField(blank=True, default='')
    allow_custom_print = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(
        default=0,
        help_text='General stock. Sellable jersey quantity lives on each size variant.',
    )
    free_shipping = models.BooleanField(
        default=False,
        help_text='Tampilkan label gratis ongkir pada kartu produk.',
    )
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(
        default=True,
        help_text='Produk yang dinonaktifkan tidak tampil di toko, tapi riwayat pesanan tetap terjaga.',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def display_image(self):
        return self.front_image or self.image

    @property
    def back_preview_image(self):
        """Foto yang dipakai untuk preview sablon nama & nomor punggung.

        Prioritas: foto punggung asli -> foto depan/utama (fallback).
        """
        return self.back_image or self.display_image

    @property
    def has_back_image(self):
        return bool(self.back_image)

    @property
    def is_jersey(self):
        if self.product_type == self.ProductType.JERSEY:
            return True
        if self.product_type in (self.ProductType.FOOTWEAR, self.ProductType.EQUIPMENT):
            return False
        cat_name = (self.category.name if self.category else '').lower()
        cat_slug = (self.category.slug if self.category else '').lower()
        return 'jersey' in cat_name or 'jersey' in cat_slug or 'jersey' in self.name.lower()

    @property
    def is_footwear(self):
        if self.product_type == self.ProductType.FOOTWEAR:
            return True
        if self.product_type in (self.ProductType.JERSEY, self.ProductType.EQUIPMENT):
            return False
        cat_name = (self.category.name if self.category else '').lower()
        cat_slug = (self.category.slug if self.category else '').lower()
        return any(w in cat_name or w in cat_slug or w in self.name.lower() for w in ['sepatu', 'footwear', 'shoes', 'cleats', 'boots', 'sneakers'])

    @property
    def is_equipment(self):
        return not self.is_jersey and not self.is_footwear

    @property
    def has_single_size(self):
        if self.is_equipment:
            return True
        variants = list(self.variants.all())
        if len(variants) == 1 and variants[0].size in ('ALL', 'One Size', 'All Size', 'OS', 'STANDAR'):
            return True
        return False

    @property
    def size_section_title(self):
        if self.is_jersey:
            return 'PILIH UKURAN JERSEY:'
        if self.is_footwear:
            return 'PILIH UKURAN SEPATU:'
        return 'SPESIFIKASI UKURAN:'

    @property
    def avg_rating(self):
        if hasattr(self, 'annotated_avg_rating'):
            val = self.annotated_avg_rating
            return round(val, 1) if val and val > 0 else None
        agg = self.ratings.aggregate(models.Avg('rating'))['rating__avg']
        return round(agg, 1) if agg is not None else None

    @property
    def total_ratings(self):
        if hasattr(self, 'annotated_rating_count'):
            return self.annotated_rating_count
        return self.ratings.count()

    @property
    def cart_additions_count(self):
        if hasattr(self, 'annotated_cart_additions'):
            return self.annotated_cart_additions
        return CartItem.objects.filter(product=self).count()


class ProductVariant(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
    )
    size = models.CharField(
        max_length=16,
        help_text='Ukuran varian, misal S, M, L, XL, XXL (jersey); 39, 40 (sepatu); ALL (peralatan/aksesoris).'
    )
    stock = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['product', 'size']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'size'],
                name='unique_product_size',
            ),
        ]

    def __str__(self):
        return f'{self.product.name} — {self.size}'


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Cart for {self.user}'

    @property
    def total(self):
        return sum((item.line_total for item in self.items.all()), Decimal('0'))


def sablon_roster_upload_path(instance, filename):
    extension = filename.rpartition('.')[2].lower()
    return f'sablon-rosters/{uuid4().hex}.{extension}'


def validate_sablon_roster(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError('Ukuran file daftar sablon maksimal 5 MB.')

    extension = upload.name.rpartition('.')[2].lower()
    header = upload.read(8)
    upload.seek(0)
    valid_headers = {
        'jpg': header.startswith(b'\xff\xd8\xff'),
        'jpeg': header.startswith(b'\xff\xd8\xff'),
        'png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        'docx': header.startswith(b'PK\x03\x04'),
        'xlsx': header.startswith(b'PK\x03\x04'),
        'doc': header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),
        'xls': header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'),
    }
    if not valid_headers.get(extension, False):
        raise ValidationError('Format file harus JPG, PNG, Word (.doc/.docx), atau Excel (.xls/.xlsx).')


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    custom_name = models.CharField(max_length=16, blank=True)
    custom_number = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(99)],
    )
    has_sablon = models.BooleanField(default=False)
    sablon_roster = models.FileField(
        upload_to=sablon_roster_upload_path,
        storage=SablonRosterStorage(),
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'doc', 'docx', 'xls', 'xlsx']),
            validate_sablon_roster,
        ],
    )
    line_key = models.CharField(max_length=80, editable=False, default='')

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['cart', 'line_key'],
                name='unique_cart_line',
            ),
        ]

    def save(self, *args, **kwargs):
        number = '' if self.custom_number is None else str(self.custom_number)
        name = (self.custom_name or '').strip().upper()
        roster_key = f'|{self.sablon_roster.name}' if self.sablon_roster else ''
        self.line_key = f'{self.variant_id}|{int(self.has_sablon)}|{name}|{number}{roster_key}'[:80]
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.quantity} × {self.variant}'

    @property
    def unit_price(self):
        price = self.product.base_price
        if self.has_sablon:
            price += Decimal(settings.SABLON_FEE)
        return price

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def sablon_total(self):
        if not self.has_sablon:
            return Decimal('0')
        return Decimal(settings.SABLON_FEE) * self.quantity


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Menunggu Pembayaran'
        PAID = 'paid', 'Sudah Dibayar'
        PROCESSING = 'processing', 'Diproses'
        SHIPPED = 'shipped', 'Perlu Dikirim / Dikirim'
        COMPLETED = 'completed', 'Selesai'
        CANCELLED = 'cancelled', 'Dibatalkan'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
        null=True,
        blank=True,
    )
    # Field untuk pesanan tamu (tanpa akun)
    guest_email = models.EmailField(blank=True, default='')
    guest_token = models.CharField(max_length=64, blank=True, default=None, unique=True, null=True)
    is_guest_order = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    address = models.TextField()
    city = models.CharField(max_length=80)
    courier = models.CharField(max_length=60, blank=True, default='')
    tracking_number = models.CharField(max_length=100, blank=True, default='')
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=0, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    stock_reserved_at = models.DateTimeField(blank=True, null=True)
    stock_released_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order #{self.pk} — {self.user or self.guest_email or "Tamu"}'

    @property
    def items_subtotal(self):
        return sum((item.line_total for item in self.items.all()), Decimal('0'))


def payment_proof_upload_path(instance, filename):
    extension = filename.rpartition('.')[2].lower()
    return f'payment-proofs/{uuid4().hex}.{extension}'


def validate_payment_proof(upload):
    if upload.size > 5 * 1024 * 1024:
        raise ValidationError('Ukuran bukti transfer maksimal 5 MB.')

    extension = upload.name.rpartition('.')[2].lower()
    header = upload.read(8)
    upload.seek(0)
    valid_headers = {
        'jpg': header.startswith(b'\xff\xd8\xff'),
        'jpeg': header.startswith(b'\xff\xd8\xff'),
        'png': header.startswith(b'\x89PNG\r\n\x1a\n'),
        'pdf': header.startswith(b'%PDF-'),
    }
    if not valid_headers.get(extension, False):
        raise ValidationError('Format bukti transfer tidak valid.')


class Payment(models.Model):
    class Method(models.TextChoices):
        MIDTRANS = 'midtrans', 'Midtrans Snap (Sandbox)'
        MANUAL_TRANSFER = 'manual_transfer', 'Transfer Bank Manual'
        LEGACY = 'legacy', 'Pembayaran Pesanan Lama'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Menunggu Pembayaran'
        AWAITING_VERIFICATION = 'awaiting_verification', 'Menunggu Verifikasi Admin'
        PAID = 'paid', 'Lunas'
        FAILED = 'failed', 'Gagal'
        EXPIRED = 'expired', 'Kedaluwarsa'
        CANCELLED = 'cancelled', 'Dibatalkan'
        REFUNDED = 'refunded', 'Dikembalikan'

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    method = models.CharField(max_length=24, choices=Method.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.PENDING)
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    gateway_order_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    gateway_transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    snap_token = models.CharField(max_length=255, blank=True, default='')
    snap_redirect_url = models.URLField(blank=True, default='')
    proof = models.FileField(
        upload_to=payment_proof_upload_path,
        storage=PrivatePaymentProofStorage(),
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'pdf']),
            validate_payment_proof,
        ],
    )
    proof_submitted_at = models.DateTimeField(blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='verified_payments',
    )
    rejection_note = models.TextField(blank=True, default='')
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment for order #{self.order_id} ({self.get_status_display()})'


class PaymentStatusHistory(models.Model):
    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name='status_history',
    )
    status = models.CharField(max_length=24, choices=Payment.Status.choices)
    note = models.CharField(max_length=255, blank=True, default='')
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='payment_status_events',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'pk']

    def __str__(self):
        return f'Payment #{self.payment_id}: {self.get_status_display()}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    product_name = models.CharField(max_length=200)
    size = models.CharField(max_length=16, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=0)
    sablon_fee = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    custom_name = models.CharField(max_length=16, blank=True)
    custom_number = models.PositiveSmallIntegerField(null=True, blank=True)
    has_sablon = models.BooleanField(default=False)
    sablon_roster = models.FileField(
        upload_to=sablon_roster_upload_path,
        storage=SablonRosterStorage(),
        blank=True,
        null=True,
    )

    def __str__(self):
        return f'{self.quantity} × {self.product_name}'

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def sablon_total(self):
        return self.sablon_fee * self.quantity

    @property
    def print_name(self):
        return self.custom_name

    @property
    def print_number(self):
        return self.custom_number


class ProductRating(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='ratings',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='product_ratings',
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        help_text='Rating 1 sampai 5 bintang'
    )
    review = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'user'],
                name='unique_product_user_rating',
            ),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.product.name} ({self.rating}★)'
