from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from store.models import Order

from .forms import ProfileForm
from .models import Profile

User = get_user_model()


class CustomerAccountTests(TestCase):
    def create_order(self, user):
        return Order.objects.create(
            user=user,
            full_name='Pelanggan',
            phone='08123456789',
            address='Jalan Uji',
            city='Jakarta',
            total=250000,
        )

    def test_customer_cannot_view_another_users_order(self):
        customer = User.objects.create_user(username='customer', password='TestPass!2026')
        another_customer = User.objects.create_user(username='other', password='TestPass!2026')
        order = self.create_order(another_customer)
        self.client.force_login(customer)

        response = self.client.get(reverse('accounts:order_detail', args=[order.pk]))

        self.assertEqual(response.status_code, 404)
        self.client.force_login(another_customer)
        self.assertEqual(
            self.client.get(reverse('accounts:orders')).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('accounts:order_detail', args=[order.pk])).status_code,
            200,
        )
        self.client.post(reverse('accounts:cancel_order', args=[order.pk]))
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(
            list(order.status_history.values_list('status', flat=True)),
            [Order.Status.PENDING, Order.Status.CANCELLED],
        )

    def test_password_change_keeps_customer_logged_in(self):
        customer = User.objects.create_user(username='customer', password='OldPass!2026')
        self.client.force_login(customer)
        self.assertEqual(self.client.get(reverse('accounts:password')).status_code, 200)

        response = self.client.post(reverse('accounts:password'), {
            'old_password': 'OldPass!2026',
            'new_password1': 'NewPass!2026!Strong',
            'new_password2': 'NewPass!2026!Strong',
        })

        self.assertRedirects(response, reverse('accounts:password'))
        self.assertEqual(self.client.get(reverse('accounts:dashboard')).status_code, 200)
        customer.refresh_from_db()
        self.assertTrue(customer.check_password('NewPass!2026!Strong'))

    def test_profile_form_rejects_non_image_avatar(self):
        customer = User.objects.create_user(username='customer', password='TestPass!2026')
        profile, _ = Profile.objects.get_or_create(user=customer)
        self.client.force_login(customer)
        self.assertEqual(self.client.get(reverse('accounts:profile')).status_code, 200)
        form = ProfileForm(
            data={
                'first_name': 'Pelanggan',
                'last_name': 'Uji',
                'email': 'customer@example.com',
                'phone': '08123456789',
                'address': 'Jalan Uji',
            },
            files={
                'avatar': SimpleUploadedFile(
                    'avatar.png',
                    b'bukan gambar',
                    content_type='image/png',
                ),
            },
            instance=customer,
            profile=profile,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('avatar', form.errors)
