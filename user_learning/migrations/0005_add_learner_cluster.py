from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_learning', '0004_add_last_practiced_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='userability',
            name='learner_cluster',
            field=models.IntegerField(null=True, blank=True),
        ),
    ]