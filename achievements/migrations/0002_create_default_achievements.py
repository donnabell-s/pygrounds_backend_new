from django.db import migrations


def create_achievements(apps, schema_editor):
    Achievement = apps.get_model('achievements', 'Achievement')
    achievements = [
        {
            'code': 'code_initiate',
            'title': 'Code Initiate',
            'description': 'Unlocked Zone 1: Python Basics. Begin your journey mastering Python fundamentals.',
            'unlocked_zone': 1,
        },
        {
            'code': 'logic_tactician',
            'title': 'Logic Tactician',
            'description': 'Unlocked Zone 2: Control Structures. Conquer decision-making and flow control.',
            'unlocked_zone': 2,
        },
        {
            'code': 'loop_virtuoso',
            'title': 'Loop Virtuoso',
            'description': 'Unlocked Zone 3: Loops & Iteration. Perfect the art of repetition and automation.',
            'unlocked_zone': 3,
        },
        {
            'code': 'system_architect',
            'title': 'System Architect',
            'description': 'Unlocked Zone 4: Data Structures & Modularity. Design organized and modular code systems.',
            'unlocked_zone': 4,
        },
    ]

    for a in achievements:
        Achievement.objects.update_or_create(code=a['code'], defaults=a)


def reverse_func(apps, schema_editor):
    Achievement = apps.get_model('achievements', 'Achievement')
    Achievement.objects.filter(code__in=['code_initiate', 'logic_tactician', 'loop_virtuoso', 'system_architect']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('achievements', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_achievements, reverse_func),
    ]
