import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from store.models import Order

from .models import LoginActivity, OrderStatusHistory, Profile
from .security import session_key_hash

logger = logging.getLogger(__name__)


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        Profile.objects.get_or_create(user=instance)


@receiver(user_logged_in)
def record_login_activity(sender, request, user, **kwargs):
    session_key = request.session.session_key
    if not session_key:
        request.session.save()
        session_key = request.session.session_key
        if not session_key:
            logger.error('Cannot record login activity: authenticated session key is missing.')
            return
    LoginActivity.objects.create(
        user=user,
        session_key_hash=session_key_hash(session_key, settings.SECRET_KEY),
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
    )


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
