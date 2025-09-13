from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ("reading", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterModelOptions(
                    name="topic",
                    options={"ordering": ["name"]},
                ),
                migrations.AlterModelOptions(
                    name="subtopic",
                    options={"ordering": ["topic__name", "order_in_topic", "name"]},
                ),
                migrations.AlterModelOptions(
                    name="readingmaterial",
                    options={"ordering": ["topic_ref__name", "subtopic_ref__order_in_topic", "title"]},
                ),
                migrations.AlterUniqueTogether(
                    name="subtopic",
                    unique_together={("topic", "slug")},
                ),
            ],
            database_operations=[],
        ),
    ]
