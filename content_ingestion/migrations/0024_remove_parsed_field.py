# Generated manually on 2025-08-12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content_ingestion', '0023_merge_20250812_1529'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='uploadeddocument',
            name='parsed',
        ),
    ]
