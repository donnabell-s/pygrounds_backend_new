from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content_ingestion', '0018_remove_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadeddocument',
            name='processing_message',
            field=models.TextField(blank=True, null=True, help_text='Detailed status message about current processing step'),
        ),
    ]
