from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_learning', '0003_userability'),
    ]

    operations = [
        migrations.AddField(
            model_name='usersubtopicmastery',
            name='last_practiced_at',
            field=models.DateTimeField(null=True, blank=True),
        ),
    ]