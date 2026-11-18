from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0004_product_product_type_alter_orderitem_size_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='free_shipping',
            field=models.BooleanField(
                default=False,
                help_text='Tampilkan label gratis ongkir pada kartu produk.',
            ),
        ),
    ]
