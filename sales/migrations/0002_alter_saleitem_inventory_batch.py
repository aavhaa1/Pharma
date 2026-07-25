from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_rename_inventory'),
        ('sales', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='saleitem',
            name='inventory_batch',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sale_items', to='inventory.inventorybatch'),
        ),
    ]
