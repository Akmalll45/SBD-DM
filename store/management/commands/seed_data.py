from django.core.management.base import BaseCommand
from django.utils.text import slugify
from store.models import Category, Product, ProductVariant


class Command(BaseCommand):
    help = 'Populates the database with realistic football jerseys, sports jerseys, and gear.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding initial categories and products...')

        categories_data = [
            {'name': 'Football Jerseys', 'slug': 'football-jerseys'},
            {'name': 'Other Sports Jerseys', 'slug': 'other-sports-jerseys'},
            {'name': 'Sports Equipment', 'slug': 'sports-equipment'},
            {'name': 'Footwear & Accessories', 'slug': 'footwear-accessories'},
        ]

        categories = {}
        for c_data in categories_data:
            cat, _ = Category.objects.get_or_create(
                slug=c_data['slug'],
                defaults={'name': c_data['name']}
            )
            categories[c_data['slug']] = cat

        products_data = [
            {
                'name': 'Real Madrid Home Jersey 24/25 Authentic',
                'category': categories['football-jerseys'],
                'base_price': 899000,
                'description': 'Jersey resmi Real Madrid kandang musim 24/25 dengan material berteknologi HEAT.RDY yang sejuk dan ringan. Siap untuk kustom sablon nama dan nomor punggung idaman Anda.',
                'is_featured': True,
                'stock': 40,
                'sizes': ['S', 'M', 'L', 'XL'],
            },
            {
                'name': 'Arsenal Home Jersey 24/25',
                'category': categories['football-jerseys'],
                'base_price': 849000,
                'description': 'Jersey kandang Arsenal dengan bordir lambang klub meriam emas ikonik. Tekstur kain premium dengan sirkulasi udara optimal.',
                'is_featured': True,
                'stock': 35,
                'sizes': ['S', 'M', 'L', 'XL'],
            },
            {
                'name': 'Timnas Indonesia Home Jersey 2024 Player Issue',
                'category': categories['football-jerseys'],
                'base_price': 799000,
                'description': 'Jersey kebanggaan Garuda dengan teknologi rajut jacquard premium. Dukung tim nasional bertanding dengan sablon custom nama & nomor pilihan.',
                'is_featured': True,
                'stock': 50,
                'sizes': ['S', 'M', 'L', 'XL'],
            },
            {
                'name': 'Barcelona Home Jersey 24/25 125th Anniversary',
                'category': categories['football-jerseys'],
                'base_price': 899000,
                'description': 'Edisi spesial 125 tahun Blaugrana dengan desain paruh warna klasik merah-biru dan sentuhan badge commemorative emas.',
                'is_featured': True,
                'stock': 25,
                'sizes': ['S', 'M', 'L', 'XL'],
            },
            {
                'name': 'Manchester City Home Jersey 24/25',
                'category': categories['football-jerseys'],
                'base_price': 849000,
                'description': 'Jersey kandang Manchester City dengan aksen grafis dial code 0161 pada kerah dan manset lengan.',
                'is_featured': True,
                'stock': 30,
                'sizes': ['S', 'M', 'L', 'XL'],
            },
            {
                'name': 'LA Lakers Statement Edition Swingman Jersey',
                'category': categories['other-sports-jerseys'],
                'base_price': 789000,
                'description': 'Jersey basket NBA Swingman warna ungu legendaris dengan konstruksi mesh ganda cepat kering.',
                'is_featured': False,
                'stock': 20,
                'sizes': ['S', 'M', 'L', 'XL'],
            },
            {
                'name': 'Indonesia Badminton Pro Player Jersey',
                'category': categories['other-sports-jerseys'],
                'base_price': 450000,
                'description': 'Jersey bulutangkis ultralight dengan aerodinamika tinggi dan kelenturan maksimal untuk smash tajam.',
                'is_featured': False,
                'stock': 30,
                'sizes': ['S', 'M', 'L', 'XL'],
            },
            {
                'name': 'Nike Flight Official Match Ball Football',
                'category': categories['sports-equipment'],
                'base_price': 650000,
                'description': 'Bola sepak standar turnamen profesional dengan alur aerowsculpt untuk stabilitas terbang bola yang konsisten.',
                'is_featured': True,
                'stock': 15,
                'sizes': ['Standard'],
            },
            {
                'name': 'Pro Carbon Shield Shin Guards',
                'category': categories['sports-equipment'],
                'base_price': 180000,
                'description': 'Pelindung tulang kering komposit karbon ringan dengan busa EVA peredam benturan keras.',
                'is_featured': False,
                'stock': 25,
                'sizes': ['M', 'L'],
            },
        ]

        for p_data in products_data:
            slug = slugify(p_data['name'])
            product, created = Product.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': p_data['name'],
                    'category': p_data['category'],
                    'base_price': p_data['base_price'],
                    'description': p_data['description'],
                    'stock': p_data['stock'],
                    'is_featured': p_data['is_featured'],
                }
            )

            # Create variants
            for size in p_data['sizes']:
                # ProductVariant choice allows S, M, L, XL
                valid_sizes = ['S', 'M', 'L', 'XL']
                size_choice = size if size in valid_sizes else 'M'
                ProductVariant.objects.get_or_create(
                    product=product,
                    size=size_choice,
                    defaults={'stock': 10}
                )

        self.stdout.write(self.style.SUCCESS('Successfully seeded sports store data!'))

