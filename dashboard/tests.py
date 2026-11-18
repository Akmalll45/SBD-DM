from django.test import TestCase

from store.models import Category, Product, ProductVariant
from .forms import ProductForm


class ProductFormTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Perlengkapan', slug='perlengkapan')

    def product_data(self, **overrides):
        data = {
            'category': self.category.pk,
            'product_type': Product.ProductType.EQUIPMENT,
            'name': 'Bola Latihan',
            'slug': 'bola-latihan',
            'base_price': '150000',
            'description': 'Bola latihan dengan permukaan bertekstur.',
            'stock_all': '12',
        }
        data.update(overrides)
        return data

    def test_equipment_form_saves_description_and_general_stock(self):
        form = ProductForm(data=self.product_data())

        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()

        self.assertEqual(product.product_type, Product.ProductType.EQUIPMENT)
        self.assertEqual(product.description, 'Bola latihan dengan permukaan bertekstur.')
        self.assertEqual(product.stock, 12)
        self.assertEqual(
            list(product.variants.values_list('size', 'stock')),
            [('ALL', 12)],
        )

    def test_changing_to_equipment_disables_old_size_stock(self):
        product = Product.objects.create(
            category=self.category,
            product_type=Product.ProductType.JERSEY,
            name='Jersey Latihan',
            slug='jersey-latihan',
            base_price=150000,
            description='Jersey latihan.',
            stock=6,
        )
        old_variant = ProductVariant.objects.create(product=product, size='S', stock=6)
        form = ProductForm(data=self.product_data(
            name='Bola Latihan Baru',
            slug='bola-latihan-baru',
            stock_all='8',
        ), instance=product)

        self.assertTrue(form.is_valid(), form.errors)
        product = form.save()

        old_variant.refresh_from_db()
        self.assertEqual(old_variant.stock, 0)
        self.assertEqual(product.stock, 8)
        self.assertEqual(product.variants.get(size='ALL').stock, 8)
