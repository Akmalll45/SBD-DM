from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm

from .models import Profile

User = get_user_model()


class ProfileForm(forms.ModelForm):
    phone = forms.CharField(
        label='Nomor telepon',
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'tel'}),
    )
    address = forms.CharField(
        label='Alamat',
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'autocomplete': 'street-address'}),
    )
    avatar = forms.ImageField(
        label='Foto profil',
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*'}),
    )
    remove_avatar = forms.BooleanField(label='Hapus foto profil', required=False)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'autocomplete': 'email'}),
        }
        labels = {
            'first_name': 'Nama depan',
            'last_name': 'Nama belakang',
            'email': 'Email',
        }

    def __init__(self, *args, profile, **kwargs):
        self.profile = profile
        super().__init__(*args, **kwargs)
        self.fields['phone'].initial = profile.phone
        self.fields['address'].initial = profile.address
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
        user = super().save(commit=commit)
        if not commit:
            return user

        old_avatar = self.profile.avatar
        new_avatar = self.cleaned_data.get('avatar')
        remove_avatar = self.cleaned_data.get('remove_avatar')

        self.profile.phone = self.cleaned_data.get('phone', '')
        self.profile.address = self.cleaned_data.get('address', '')
        if remove_avatar:
            self.profile.avatar = None
        elif new_avatar:
            self.profile.avatar = new_avatar
        self.profile.save()

        saved_avatar_name = self.profile.avatar.name if self.profile.avatar else None
        if old_avatar and (remove_avatar or new_avatar) and old_avatar.name != saved_avatar_name:
            old_avatar.delete(save=False)
        return user


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
