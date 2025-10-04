from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('achievements', '0003_add_more_achievements'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserAchievement',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('unlocked_at', models.DateTimeField(auto_now_add=True)),
                ('achievement', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='user_achievements', to='achievements.achievement')),
                ('user', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='achievements', to='users.user')),
            ],
            options={
                'ordering': ['-unlocked_at'],
                'unique_together': {('user', 'achievement')},
            },
        ),
    ]
