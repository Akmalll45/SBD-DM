from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from store.models import Order

from .models import OrderStatusHistory, Profile


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        Profile.objects.get_or_create(user=instance)


@receiver(pre_save, sender=Order)
def remember_order_status(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        instance._previous_status = None
        return
    instance._previous_status = (
        sender.objects.filter(pk=instance.pk)
        .values_list('status', flat=True)
        .first()
    )


@receiver(post_save, sender=Order)
def record_order_status(sender, instance, created, raw=False, **kwargs):
    if raw:
        return

    if created:
        OrderStatusHistory.objects.create(
            order=instance,
            status=instance.status,
            note='Pesanan dibuat',
        )
        return

    previous_status = getattr(instance, '_previous_status', None)
    if not previous_status or previous_status == instance.status:
        return

    history = OrderStatusHistory.objects.filter(order=instance)
    if not history.exists():
        OrderStatusHistory.objects.create(
            order=instance,
            status=previous_status,
            created_at=instance.created_at,
            note='Status awal',
        )
    OrderStatusHistory.objects.create(order=instance, status=instance.status)
