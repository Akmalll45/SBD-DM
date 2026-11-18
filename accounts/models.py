from django.conf import settings
from django.db import models
from django.utils import timezone

from store.models import Order


class Profile(models.Model):
    class Gender(models.TextChoices):
        WOMAN = 'woman', 'Perempuan'
        MAN = 'man', 'Laki-laki'
        OTHER = 'other', 'Lainnya'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    phone = models.CharField(max_length=30, blank=True, default='')
    address = models.TextField(blank=True, default='')
    avatar = models.ImageField(upload_to='accounts/avatars/', blank=True, null=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, blank=True, default='')
    birth_date = models.DateField(blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    phone_otp_hash = models.CharField(max_length=128, blank=True, default='')
    phone_otp_sent_at = models.DateTimeField(blank=True, null=True)
    phone_otp_attempts = models.PositiveSmallIntegerField(default=0)
    totp_enabled = models.BooleanField(default=False)
    totp_secret = models.CharField(max_length=64, blank=True, default='')
    totp_pending_secret = models.CharField(max_length=64, blank=True, default='')
    totp_last_counter = models.BigIntegerField(default=-1)
    totp_attempts = models.PositiveSmallIntegerField(default=0)
    totp_lockout_until = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'Profil {self.user}'


class Address(models.Model):
    class Label(models.TextChoices):
        HOME = 'home', 'Rumah'
        OFFICE = 'office', 'Kantor'
        OTHER = 'other', 'Lainnya'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_addresses',
    )
    label = models.CharField(max_length=20, choices=Label.choices, default=Label.HOME)
    custom_label = models.CharField(max_length=40, blank=True, default='')
    recipient_name = models.CharField(max_length=120)
    recipient_phone = models.CharField(max_length=30)
    province = models.CharField(max_length=80)
    city = models.CharField(max_length=80)
    district = models.CharField(max_length=80)
    subdistrict = models.CharField(max_length=80)
    postal_code = models.CharField(max_length=10)
    detail_address = models.TextField()
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_primary', '-updated_at']
        verbose_name_plural = 'addresses'

    @property
    def display_label(self):
        return self.custom_label if self.label == self.Label.OTHER and self.custom_label else self.get_label_display()

    def __str__(self):
        return f'{self.display_label} — {self.recipient_name}'


class LoginActivity(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='login_activities',
    )
    session_key_hash = models.CharField(max_length=64, blank=True, default='')
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_history',
    )
    status = models.CharField(max_length=20, choices=Order.Status.choices)
    created_at = models.DateTimeField(default=timezone.now)
    note = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        ordering = ['created_at', 'pk']
        verbose_name_plural = 'order status histories'

    def __str__(self):
        return f'Order #{self.order_id}: {self.get_status_display()}'
