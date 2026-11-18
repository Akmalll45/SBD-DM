from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core import signing
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from unittest.mock import patch

from store.models import Order

from .forms import AddressForm, ProfileForm
from .models import Address, LoginActivity, Profile
from .security import matching_totp_counter

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


class AccountProfileFeatureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='customer',
            email='customer@example.com',
            password='TestPass!2026',
        )
        self.profile, _ = Profile.objects.get_or_create(user=self.user)
        self.client.force_login(self.user)

    def address_data(self, **overrides):
        data = {
            'label': Address.Label.HOME,
            'custom_label': '',
            'recipient_name': 'Pelanggan',
            'recipient_phone': '+628123456789',
            'province': 'Jawa Barat',
            'city': 'Bandung',
            'district': 'Coblong',
            'subdistrict': 'Dago',
            'postal_code': '40135',
            'detail_address': 'Jalan Uji nomor 1',
            'is_primary': 'on',
        }
        data.update(overrides)
        return data

    def test_profile_saves_editable_identity_and_optional_details(self):
        response = self.client.post(reverse('accounts:profile'), {
            'username': 'customer-updated',
            'first_name': 'Nama',
            'last_name': 'Baru',
            'email': 'new@example.com',
            'phone': '08123456789',
            'gender': Profile.Gender.WOMAN,
            'birth_date': '1998-04-12',
        })

        self.assertRedirects(response, reverse('accounts:profile'))
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(self.user.username, 'customer-updated')
        self.assertFalse(self.profile.email_verified)
        self.assertEqual(self.profile.gender, Profile.Gender.WOMAN)
        self.assertEqual(str(self.profile.birth_date), '1998-04-12')

    def test_address_book_can_set_a_primary_address(self):
        response = self.client.post(reverse('accounts:address_add'), self.address_data())
        self.assertRedirects(response, reverse('accounts:profile'))
        address = Address.objects.get(user=self.user)
        self.assertTrue(address.is_primary)

        response = self.client.post(
            reverse('accounts:address_add'),
            self.address_data(label=Address.Label.OFFICE, is_primary=''),
        )
        self.assertRedirects(response, reverse('accounts:profile'))
        second_address = Address.objects.exclude(pk=address.pk).get(user=self.user)
        self.assertFalse(second_address.is_primary)

        response = self.client.post(
            reverse('accounts:address_set_primary', args=[second_address.pk]),
        )
        self.assertRedirects(response, reverse('accounts:profile'))
        address.refresh_from_db()
        second_address.refresh_from_db()
        self.assertFalse(address.is_primary)
        self.assertTrue(second_address.is_primary)

    def test_phone_verification_accepts_valid_unexpired_code(self):
        self.profile.phone = '+628123456789'
        self.profile.phone_otp_hash = make_password('123456')
        self.profile.phone_otp_sent_at = timezone.now()
        self.profile.save()

        response = self.client.post(reverse('accounts:verify_phone'), {'code': '123456'})

        self.assertRedirects(response, reverse('accounts:profile'))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.phone_verified)
        self.assertEqual(self.profile.phone_otp_hash, '')

    def test_signed_email_verification_marks_current_email_verified(self):
        token = signing.dumps(
            {'user_id': self.user.pk, 'email': self.user.email},
            salt='accounts.email-verification',
        )

        response = self.client.get(reverse('accounts:verify_email', kwargs={'token': token}))

        self.assertRedirects(response, reverse('accounts:profile'))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.email_verified)

    @patch('accounts.views.matching_totp_counter', return_value=12345)
    def test_two_factor_challenge_finishes_login_and_records_activity(self, verify_code):
        self.client.logout()
        LoginActivity.objects.filter(user=self.user).delete()
        self.profile.totp_enabled = True
        self.profile.totp_secret = 'JBSWY3DPEHPK3PXP'
        self.profile.save()

        response = self.client.post(reverse('store:login'), {
            'username': self.user.username,
            'password': 'TestPass!2026',
        })
        self.assertRedirects(response, reverse('accounts:totp_login'))
        self.assertNotIn('_auth_user_id', self.client.session)

        response = self.client.post(reverse('accounts:totp_login'), {'code': '123456'})

        self.assertRedirects(response, reverse('store:home'))
        self.assertEqual(self.client.session.get('_auth_user_id'), str(self.user.pk))
        activity = LoginActivity.objects.get(user=self.user)
        self.assertNotEqual(activity.session_key_hash, self.client.session.session_key)
        verify_code.assert_called_once()

    def test_address_form_requires_custom_label_for_other(self):
        form = AddressForm(self.address_data(label=Address.Label.OTHER, custom_label=''))

        self.assertFalse(form.is_valid())
        self.assertIn('custom_label', form.errors)

    def test_totp_matches_sha1_standard_vector(self):
        secret = 'GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ'

        self.assertEqual(matching_totp_counter(secret, '287082', now=59), 1)
        self.assertIsNone(matching_totp_counter(secret, 'not-a-code', now=59))

    def test_logout_other_devices_preserves_current_session(self):
        other_client = Client()
        other_client.force_login(self.user)

        response = self.client.post(reverse('accounts:logout_other_devices'))

        self.assertRedirects(response, reverse('accounts:security'))
        self.assertEqual(self.client.get(reverse('accounts:dashboard')).status_code, 200)
        self.assertRedirects(
            other_client.get(reverse('accounts:dashboard')),
            f'{reverse("store:login")}?next={reverse("accounts:dashboard")}',
        )

    def test_security_settings_page_renders_totp_setup(self):
        self.profile.totp_pending_secret = 'TESTSECRET'
        self.profile.save(update_fields=['totp_pending_secret'])

        response = self.client.get(reverse('accounts:security'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'TESTSECRET')
