from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('content_ingestion', '0001_initial'),
        ('user_learning', '0002_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UserTopicProficiencyHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('proficiency_percent', models.FloatField()),
                ('recorded_at', models.DateTimeField(auto_now_add=True)),
                ('topic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='content_ingestion.topic')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='topic_proficiency_history', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['recorded_at'],
            },
        ),
        migrations.AddIndex(
            model_name='usertopicproficiencyhistory',
            index=models.Index(fields=['user', 'topic', 'recorded_at'], name='user_learni_user_id_topicid_recorded_idx'),
        ),
    ]
