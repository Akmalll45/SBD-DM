from decimal import Decimal
from django import forms
from django.utils.text import slugify

from store.forms import OrderStatusForm
from store.models import Category, Product, ProductVariant
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
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'bola-latihan-2025 (opsional)'})
    )

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
    stock_39 = forms.IntegerField(
        label='Stok Sepatu 39', min_value=0, initial=0, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input'}),
    )
    stock_40 = forms.IntegerField(
        label='Stok Sepatu 40', min_value=0, initial=0, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input'}),
    )
    stock_41 = forms.IntegerField(
        label='Stok Sepatu 41', min_value=0, initial=0, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input'}),
    )
    stock_42 = forms.IntegerField(
        label='Stok Sepatu 42', min_value=0, initial=0, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input'}),
    )
    stock_43 = forms.IntegerField(
        label='Stok Sepatu 43', min_value=0, initial=0, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input'}),
    )
    stock_44 = forms.IntegerField(
        label='Stok Sepatu 44', min_value=0, initial=0, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input'}),
    )
    stock_all = forms.IntegerField(
        label='Stok produk',
        min_value=0,
        initial=0,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Jumlah stok'}),
    )

    class Meta:
        model = Product
        fields = [
            'category',
            'product_type',
            'name',
            'slug',
            'base_price',
            'description',
            'image',
            'back_image',
            'free_shipping',
            'is_featured',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'product_type': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Contoh: Bola Latihan atau Sepatu Olahraga'}),
            'base_price': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '849000'}),
            'description': forms.Textarea(attrs={'class': 'form-textarea', 'rows': 4, 'placeholder': 'Jelaskan deskripsi dan spesifikasi produk...'}),
            'image': forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*'}),
            'back_image': forms.FileInput(attrs={'class': 'form-file-input', 'accept': 'image/*'}),
            'free_shipping': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        labels = {
            'category': 'Kategori Produk',
            'product_type': 'Jenis Produk',
            'name': 'Nama Produk',
            'slug': 'Slug URL (Opsional)',
            'base_price': 'Harga Dasar (Rp)',
            'description': 'Deskripsi Lengkap',
            'image': 'Foto Produk',
            'back_image': 'Foto Punggung Jersey (untuk preview nama & nomor)',
            'free_shipping': 'Tampilkan label Gratis Ongkir pada produk ini',
            'is_featured': 'Tampilkan di Bagian Featured (Beranda)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_product_type = self.instance.product_type if self.instance.pk else None
        if self.instance and self.instance.pk:
            variants = list(self.instance.variants.all())
            for variant in variants:
                size_lower = variant.size.lower()
                field_name = f'stock_{size_lower}'
                if field_name in self.fields:
                    self.initial[field_name] = variant.stock
            if self.instance.product_type == Product.ProductType.EQUIPMENT:
                single_size_variant = next(
                    (
                        variant for variant in variants
                        if variant.size.strip().upper() in ('ALL', 'ONE SIZE', 'ALL SIZE', 'OS', 'STANDAR')
                    ),
                    None,
                )
                self.initial['stock_all'] = (
                    single_size_variant.stock if single_size_variant else self.instance.stock
                )

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
        if product.product_type == Product.ProductType.JERSEY:
            variant_data = {
                'S': self.cleaned_data.get('stock_s') or 0,
                'M': self.cleaned_data.get('stock_m') or 0,
                'L': self.cleaned_data.get('stock_l') or 0,
                'XL': self.cleaned_data.get('stock_xl') or 0,
            }
        elif product.product_type == Product.ProductType.FOOTWEAR:
            variant_data = {
                str(size): self.cleaned_data.get(f'stock_{size}') or 0
                for size in range(39, 45)
            }
        else:
            variant_data = {'ALL': self.cleaned_data.get('stock_all') or 0}

        product.stock = sum(variant_data.values())

        if commit:
            product.save()
            if self.original_product_type and self.original_product_type != product.product_type:
                ProductVariant.objects.filter(product=product).exclude(
                    size__in=variant_data
                ).update(stock=0)
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
