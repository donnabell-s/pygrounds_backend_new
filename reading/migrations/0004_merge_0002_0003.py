from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("reading", "0002_remove_subtopic_uniq_topic_subtopic_and_more"),
        ("reading", "0003_fix_existing_timestamps"),
    ]

    operations = []