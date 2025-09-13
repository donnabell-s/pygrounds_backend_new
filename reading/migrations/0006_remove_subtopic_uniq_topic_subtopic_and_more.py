from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("reading", "0005_backfill_timestamps"),  
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterUniqueTogether(
                    name="subtopic",
                    unique_together={("topic", "slug")},
                ),
            ],
            database_operations=[],
        ),
    ]
