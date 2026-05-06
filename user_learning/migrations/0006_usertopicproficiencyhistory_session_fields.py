from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_learning', '0003_usertopicproficiencyhistory'),
        ('user_learning', '0005_add_learner_cluster'),
    ]

    operations = [
        migrations.AddField(
            model_name='usertopicproficiencyhistory',
            name='session_id',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name='usertopicproficiencyhistory',
            name='is_pre_session',
            field=models.BooleanField(default=False),
        ),
    ]
