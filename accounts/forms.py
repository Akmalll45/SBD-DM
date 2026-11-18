from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm

from .models import Address, Profile

User = get_user_model()


class ProfileForm(forms.ModelForm):
    username = forms.CharField(
        label='Username',
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'username'}),
    )
    phone = forms.CharField(
        label='Nomor telepon / WhatsApp',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'tel'}),
    )
    gender = forms.ChoiceField(
        label='Jenis kelamin (opsional)',
        choices=[('', 'Pilih jenis kelamin'), *Profile.Gender.choices],
        required=False,
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    birth_date = forms.DateField(
        label='Tanggal lahir (opsional)',
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date', 'autocomplete': 'bday'}),
    )
    avatar = forms.ImageField(
        label='Foto profil',
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*'}),
    )
    remove_avatar = forms.BooleanField(label='Hapus foto profil', required=False)

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'username'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'autocomplete': 'email'}),
        }
        labels = {
            'username': 'Username',
            'first_name': 'Nama depan',
            'last_name': 'Nama belakang',
            'email': 'Email',
        }

    def __init__(self, *args, profile, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        self.fields['phone'].initial = profile.phone
        self.fields['gender'].initial = profile.gender
        self.fields['birth_date'].initial = profile.birth_date
        self.fields['avatar'].initial = profile.avatar

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Email ini sudah digunakan oleh akun lain.')
        return email

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and avatar.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Ukuran foto maksimal 2 MB.')
        return avatar

    def save(self, commit=True):
        old_email = self.instance.email
        old_phone = self.profile.phone
        user = super().save(commit=commit)
        if not commit:
            return user

        old_avatar = self.profile.avatar
        new_avatar = self.cleaned_data.get('avatar')
        remove_avatar = self.cleaned_data.get('remove_avatar')

        self.profile.phone = self.cleaned_data.get('phone', '')
        self.profile.gender = self.cleaned_data.get('gender', '')
        self.profile.birth_date = self.cleaned_data.get('birth_date')
        update_fields = ['phone', 'gender', 'birth_date']
        if old_email != user.email:
            self.profile.email_verified = False
            update_fields.append('email_verified')
        if old_phone != self.profile.phone:
            self.profile.phone_verified = False
            self.profile.phone_otp_hash = ''
            self.profile.phone_otp_sent_at = None
            self.profile.phone_otp_attempts = 0
            update_fields.extend([
                'phone_verified',
                'phone_otp_hash',
                'phone_otp_sent_at',
                'phone_otp_attempts',
            ])
        if remove_avatar:
            self.profile.avatar = None
            update_fields.append('avatar')
        elif new_avatar:
            self.profile.avatar = new_avatar
            update_fields.append('avatar')
        self.profile.save(update_fields=update_fields)

        saved_avatar_name = self.profile.avatar.name if self.profile.avatar else None
        if old_avatar and (remove_avatar or new_avatar) and old_avatar.name != saved_avatar_name:
            old_avatar.delete(save=False)
        return user


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            'label',
            'custom_label',
            'recipient_name',
            'recipient_phone',
            'province',
            'city',
            'district',
            'subdistrict',
            'postal_code',
            'detail_address',
            'is_primary',
        ]
        widgets = {
            'label': forms.Select(attrs={'class': 'form-input'}),
            'custom_label': forms.TextInput(attrs={'class': 'form-input'}),
            'recipient_name': forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'name'}),
            'recipient_phone': forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'tel'}),
            'province': forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'address-level1'}),
            'city': forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'address-level2'}),
            'district': forms.TextInput(attrs={'class': 'form-input'}),
            'subdistrict': forms.TextInput(attrs={'class': 'form-input'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'postal-code'}),
            'detail_address': forms.Textarea(attrs={
                'class': 'form-textarea',
                'rows': 3,
                'autocomplete': 'street-address',
            }),
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        labels = {
            'label': 'Label alamat',
            'custom_label': 'Nama label',
            'recipient_name': 'Nama penerima',
            'recipient_phone': 'Nomor telepon penerima',
            'province': 'Provinsi',
            'city': 'Kabupaten / Kota',
            'district': 'Kecamatan',
            'subdistrict': 'Kelurahan',
            'postal_code': 'Kode pos',
            'detail_address': 'Detail alamat',
            'is_primary': 'Jadikan alamat utama',
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('label') == Address.Label.OTHER and not cleaned_data.get('custom_label', '').strip():
            self.add_error('custom_label', 'Isi nama label alamat lainnya.')
        return cleaned_data


class VerificationCodeForm(forms.Form):
    code = forms.RegexField(
        regex=r'^\d{6}$',
        label='Kode verifikasi 6 digit',
        error_messages={'invalid': 'Masukkan kode verifikasi 6 digit.'},
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
            'maxlength': '6',
        }),
    )


class IndonesianPasswordChangeForm(PasswordChangeForm):
    error_messages = {
        **PasswordChangeForm.error_messages,
        'password_incorrect': 'Kata sandi lama yang Anda masukkan salah.',
        'password_mismatch': 'Konfirmasi kata sandi baru tidak cocok.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Kata sandi lama'
        self.fields['new_password1'].label = 'Kata sandi baru'
        self.fields['new_password2'].label = 'Konfirmasi kata sandi baru'
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-input'
