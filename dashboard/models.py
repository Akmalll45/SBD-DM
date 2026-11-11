from decimal import Decimal
from django.db import models
from django.utils.text import slugify


class SiteSetting(models.Model):
    site_name = models.CharField(max_length=100, default='Hendra Sport')
    tagline = models.CharField(max_length=200, default='Gear Up. Push Your Limits.')
    contact_email = models.EmailField(default='support@hendrasport.com')
    contact_phone = models.CharField(max_length=30, default='+62 812-3456-7890')
    contact_address = models.TextField(blank=True, default='Jl. Sudirman No. 45, Jakarta Selatan')
    logo = models.ImageField(upload_to='site/', blank=True, null=True)
    sablon_fee = models.DecimalField(max_digits=10, decimal_places=0, default=Decimal('75000'))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Site Setting'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return f"{self.site_name} Settings"

    def save(self, *args, **kwargs):
        # Force single instance
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'site_name': 'Hendra Sport',
                'tagline': 'Gear Up. Push Your Limits.',
                'contact_email': 'support@hendrasport.com',
                'contact_phone': '+62 812-3456-7890',
            }
        )
        return obj


class Article(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    cover_image = models.ImageField(upload_to='articles/', blank=True, null=True)
    excerpt = models.TextField(blank=True, help_text='Ringkasan singkat artikel untuk preview.')
    content = models.TextField(help_text='Isi lengkap artikel/berita olahraga.')
    is_published = models.BooleanField(default=True, help_text='Centang untuk mempublikasikan artikel.')
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Article'
        verbose_name_plural = 'Articles'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title) or 'article'
            slug = base_slug
            counter = 1
            while Article.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
