from decimal import Decimal
from django import forms
from django.utils.text import slugify

from store.models import Category, Product, ProductVariant, Order
from .models import SiteSetting, Article


class SiteSettingForm(forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = [
            'site_name',
            'tagline',
            'contact_email',
            'contact_phone',
            'contact_address',
            'logo',
            'sablon_fee',
        ]
        widgets = {
            'site_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Nama Toko Olahraga'}),
            'tagline': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Slogan / Tagline'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'email@toko.com'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': '+62 812-xxxx-xxxx'}),
            'contact_address': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 3, 'placeholder': 'Alamat toko / operasional'}),
            'logo': forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*'}),
            'sablon_fee': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '75000'}),
        }
        labels = {
            'site_name': 'Nama Website / Brand',
            'tagline': 'Tagline Toko',
            'contact_email': 'Email Kontak',
            'contact_phone': 'Nomor Telepon / WhatsApp',
            'contact_address': 'Alamat Kantor / Toko',
            'logo': 'Upload Logo Brand (PNG / JPG / WEBP)',
            'sablon_fee': 'Tarif Flat Custom Sablon (Rp)',
        }


class ArticleForm(forms.ModelForm):
    slug = forms.SlugField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'otomatis-terisi-jika-kosong'})
    )

    class Meta:
        model = Article
        fields = ['title', 'slug', 'cover_image', 'excerpt', 'content', 'is_published']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Judul Berita / Rilis Jersey Baru'}),
            'cover_image': forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*'}),
            'excerpt': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 2, 'placeholder': 'Ringkasan singkat artikel...'}),
            'content': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 8, 'placeholder': 'Tulis isi artikel lengkap...'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        labels = {
            'title': 'Judul Artikel',
            'slug': 'Slug URL (Opsional)',
            'cover_image': 'Cover Gambar Artikel',
            'excerpt': 'Ringkasan / Excerpt',
            'content': 'Konten Lengkap',
            'is_published': 'Publikasikan Sekarang',
        }


class ProductForm(forms.ModelForm):
    slug = forms.SlugField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'arsenal-home-jersey-2425 (opsional)'})
    )

    # Specialized Size Variant Stock fields for convenient management
    stock_s = forms.IntegerField(
        label='Stok Ukuran S',
        min_value=0,
        initial=10,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Stok S'})
    )
    stock_m = forms.IntegerField(
        label='Stok Ukuran M',
        min_value=0,
        initial=10,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Stok M'})
    )
    stock_l = forms.IntegerField(
        label='Stok Ukuran L',
        min_value=0,
        initial=10,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Stok L'})
    )
    stock_xl = forms.IntegerField(
        label='Stok Ukuran XL',
        min_value=0,
        initial=10,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Stok XL'})
    )

    class Meta:
        model = Product
        fields = [
            'category',
            'name',
            'slug',
            'base_price',
            'description',
            'image',
            'back_image',
            'is_featured',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Contoh: Arsenal Home Jersey 24/25'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '849000'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'Deskripsi bahan, spesifikasi, dan keunggulan jersey...'}),
            'image': forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*'}),
            'back_image': forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        labels = {
            'category': 'Kategori Produk',
            'name': 'Nama Produk / Jersey',
            'slug': 'Slug URL (Opsional)',
            'base_price': 'Harga Dasar (Rp)',
            'description': 'Deskripsi Lengkap',
            'image': 'Foto Produk',
            'back_image': 'Foto Punggung Jersey (untuk preview nama & nomor)',
            'is_featured': 'Tampilkan di Bagian Featured (Beranda)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Populate existing variant stock
            for variant in self.instance.variants.all():
                size_lower = variant.size.lower()
                field_name = f'stock_{size_lower}'
                if field_name in self.fields:
                    self.initial[field_name] = variant.stock

    def clean(self):
        cleaned_data = super().clean()
        slug = cleaned_data.get('slug')
        name = cleaned_data.get('name')
        if not slug and name:
            base_slug = slugify(name) or 'product'
            slug = base_slug
            counter = 1
            pk = self.instance.pk if self.instance else None
            while Product.objects.filter(slug=slug).exclude(pk=pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            cleaned_data['slug'] = slug
        return cleaned_data

    def save(self, commit=True):
        product = super().save(commit=False)
        # Compute general stock as sum of variants
        s = self.cleaned_data.get('stock_s') or 0
        m = self.cleaned_data.get('stock_m') or 0
        l = self.cleaned_data.get('stock_l') or 0
        xl = self.cleaned_data.get('stock_xl') or 0
        product.stock = s + m + l + xl

        if commit:
            product.save()
            # Update/create variants for sizes S, M, L, XL
            variant_data = {'S': s, 'M': m, 'L': l, 'XL': xl}
            for size, qty in variant_data.items():
                ProductVariant.objects.update_or_create(
                    product=product,
                    size=size,
                    defaults={'stock': qty}
                )

        return product


class ProductVariantForm(forms.ModelForm):
    class Meta:
        model = ProductVariant
        fields = ['size', 'stock']
        widgets = {
            'size': forms.Select(attrs={'class': 'form-select'}),
            'stock': forms.NumberInput(attrs={'class': 'form-input'}),
        }


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
        }
