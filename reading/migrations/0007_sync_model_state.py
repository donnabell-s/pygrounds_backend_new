from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("reading", "0006_remove_subtopic_uniq_topic_subtopic_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="subtopic",
                    name="slug",
                    field=models.SlugField(max_length=255),
                ),
                migrations.AlterField(
                    model_name="topic",
                    name="name",
                    field=models.CharField(max_length=255),
                ),
                migrations.AlterField(
                    model_name="topic",
                    name="slug",
                    field=models.SlugField(max_length=255, unique=True),
                ),
            ],
            database_operations=[],
        ),
    ]