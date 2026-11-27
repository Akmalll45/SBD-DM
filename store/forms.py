from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.conf import settings

from .models import Order, Payment


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username',
            'autofocus': True,
        })
        self.fields['email'].widget.attrs.update({'autocomplete': 'email'})
        self.fields['password1'].widget.attrs.update({'autocomplete': 'new-password'})
        self.fields['password2'].widget.attrs.update({'autocomplete': 'new-password'})
        for field in self.fields.values():
            field.help_text = ''

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username',
            'autofocus': True,
        })
        self.fields['password'].widget.attrs.update({'autocomplete': 'current-password'})


class CheckoutShippingForm(forms.Form):
    full_name = forms.CharField(
        max_length=120,
        label='Nama penerima',
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'name'}),
    )
    phone = forms.CharField(
        max_length=30,
        label='Nomor telepon',
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'tel'}),
    )
    city = forms.CharField(
        max_length=80,
        label='Kota / kabupaten',
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'address-level2'}),
    )
    address = forms.CharField(
        label='Alamat lengkap',
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'form-textarea',
            'autocomplete': 'street-address',
        }),
    )
    courier = forms.ChoiceField(
        label='Layanan pengiriman',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        shipping_options = kwargs.pop('shipping_options')
        super().__init__(*args, **kwargs)
        self.fields['courier'].choices = [
            (code, f'{label} — Rp {amount:,.0f}'.replace(',', '.'))
            for code, label, amount in shipping_options
        ]


class GuestCheckoutForm(forms.Form):
    """Form untuk pembelian tamu (tanpa akun) — 1 produk langsung."""
    full_name = forms.CharField(
        max_length=120, label='Nama penerima',
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'name', 'placeholder': 'Nama lengkap'}),
    )
    email = forms.EmailField(
        label='Email (untuk konfirmasi pesanan)',
        widget=forms.EmailInput(attrs={'class': 'form-input', 'autocomplete': 'email', 'placeholder': 'email@contoh.com'}),
    )
    phone = forms.CharField(
        max_length=30, label='Nomor telepon / WhatsApp',
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'tel', 'placeholder': '08xxxxxxxxxx'}),
    )
    city = forms.CharField(
        max_length=80, label='Kota / kabupaten',
        widget=forms.TextInput(attrs={'class': 'form-input', 'autocomplete': 'address-level2', 'placeholder': 'Kota tujuan pengiriman'}),
    )
    address = forms.CharField(
        label='Alamat lengkap',
        widget=forms.Textarea(attrs={
            'rows': 3, 'class': 'form-textarea',
            'autocomplete': 'street-address',
            'placeholder': 'Jalan, RT/RW, Kelurahan, Kecamatan...',
        }),
    )
    courier = forms.ChoiceField(
        label='Layanan pengiriman',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    quantity = forms.IntegerField(
        min_value=1, max_value=99, initial=1, label='Jumlah',
        widget=forms.NumberInput(attrs={'class': 'form-input', 'min': '1', 'max': '99'}),
    )
    variant_id = forms.IntegerField(required=False, widget=forms.HiddenInput())
    has_sablon = forms.BooleanField(required=False, label='Custom Sablon Nama & Nomor')
    custom_name = forms.CharField(
        max_length=16, required=False, label='Nama Punggung',
        widget=forms.TextInput(attrs={
            'class': 'form-input', 'maxlength': '16',
            'placeholder': 'CONTOH: RONALDO',
            'style': 'text-transform: uppercase;',
        }),
    )
    custom_number = forms.IntegerField(
        min_value=0, max_value=99, required=False, label='Nomor Punggung',
        widget=forms.NumberInput(attrs={
            'class': 'form-input', 'min': '0', 'max': '99',
            'placeholder': 'CONTOH: 7',
        }),
    )
    sablon_roster = forms.FileField(required=False, label='Daftar Nama & Nomor Sablon')

    def __init__(self, *args, **kwargs):
        shipping_options = kwargs.pop('shipping_options', [])
        super().__init__(*args, **kwargs)
        self.fields['courier'].choices = [
            (code, f'{label} — Rp {amount:,.0f}'.replace(',', '.'))
            for code, label, amount in shipping_options
        ]


class PaymentProofForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['proof']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proof'].widget.attrs.update({
            'accept': '.jpg,.jpeg,.png,.pdf',
            'class': 'form-input',
        })
        self.fields['proof'].required = True


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status', 'courier', 'tracking_number']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'courier': forms.TextInput(attrs={'class': 'form-input'}),
            'tracking_number': forms.TextInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = Order.Status.choices

    def clean_status(self):
        status = self.cleaned_data['status']
        payment = getattr(self.instance, 'payment', None)
        if self.instance.status == Order.Status.CANCELLED and status != Order.Status.CANCELLED:
            raise forms.ValidationError('Pesanan yang sudah dibatalkan tidak dapat diaktifkan kembali.')
        if (
            status == Order.Status.PENDING
            and payment
            and payment.status == Payment.Status.PAID
        ):
            raise forms.ValidationError('Pesanan lunas tidak dapat dikembalikan ke status menunggu pembayaran.')
        return status
