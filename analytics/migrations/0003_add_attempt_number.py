from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='questionresponse',
            name='attempt_number',
            field=models.PositiveIntegerField(null=True, blank=True),
        ),
    ]
