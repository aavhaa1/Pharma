from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('medicines', '0001_initial'),
        ('inventory', '0002_inventoryhistory_notes'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='Inventory',
            new_name='InventoryBatch',
        ),
        migrations.AlterModelOptions(
            name='inventorybatch',
            options={'ordering': ['expiry_date'], 'verbose_name': 'Inventory Batch', 'verbose_name_plural': 'Inventory Batches'},
        ),
        migrations.CreateModel(
            name='Inventory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('current_stock', models.PositiveIntegerField(default=0, verbose_name='Current Stock')),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('medicine', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='inventory_record', to='medicines.medicine', verbose_name='Medicine')),
            ],
            options={
                'verbose_name': 'Inventory',
                'verbose_name_plural': 'Inventories',
            },
        ),
    ]
