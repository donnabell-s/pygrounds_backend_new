from django.db import migrations


def create_more_achievements(apps, schema_editor):
    Achievement = apps.get_model('achievements', 'Achievement')
    achievements = [
        {
            'code': 'game_enthusiast',
            'title': 'Game Enthusiast',
            'description': 'Play 20 games across any minigame. Keep the momentum going!',
            'unlocked_zone': None,
        },
        {
            'code': 'perfection_seeker',
            'title': 'Perfection Seeker',
            'description': 'Perfect 5 games with flawless performance. Precision pays off!',
            'unlocked_zone': None,
        },
        {
            'code': 'speed_solver',
            'title': 'Speed Solver',
            'description': 'Perfect a non-coding game in under one minute. Lightning-fast mastery!',
            'unlocked_zone': None,
        },
    ]

    for a in achievements:
        Achievement.objects.update_or_create(code=a['code'], defaults=a)


def reverse_func(apps, schema_editor):
    Achievement = apps.get_model('achievements', 'Achievement')
    Achievement.objects.filter(code__in=['game_enthusiast', 'perfection_seeker', 'speed_solver']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('achievements', '0002_create_default_achievements'),
    ]

    operations = [
        migrations.RunPython(create_more_achievements, reverse_func),
    ]
