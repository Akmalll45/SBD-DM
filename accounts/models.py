from django.conf import settings
from django.db import models
from django.utils import timezone

from store.models import Order


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    phone = models.CharField(max_length=30, blank=True, default='')
    address = models.TextField(blank=True, default='')
    avatar = models.ImageField(upload_to='accounts/avatars/', blank=True, null=True)

    def __str__(self):
        return f'Profil {self.user}'


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
