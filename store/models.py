from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
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
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def display_image(self):
        return self.front_image or self.image


class ProductVariant(models.Model):
    class Size(models.TextChoices):
        S = 'S', 'S'
        M = 'M', 'M'
        L = 'L', 'L'
        XL = 'XL', 'XL'

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='variants',
    )
    size = models.CharField(max_length=4, choices=Size.choices)
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
        self.line_key = f'{self.variant_id}|{int(self.has_sablon)}|{name}|{number}'
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
    )
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
    total = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order #{self.pk} — {self.user}'


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
    size = models.CharField(max_length=8, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=0)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    custom_name = models.CharField(max_length=16, blank=True)
    custom_number = models.PositiveSmallIntegerField(null=True, blank=True)
    has_sablon = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.quantity} × {self.product_name}'

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def print_name(self):
        return self.custom_name

    @property
    def print_number(self):
        return self.custom_number
