from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ("reading", "0002_remove_subtopic_uniq_topic_subtopic_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="topic",
                    name="created_at",
                    field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
                ),
                migrations.AddField(
                    model_name="topic",
                    name="updated_at",
                    field=models.DateTimeField(auto_now=True, null=True, blank=True),
                ),
                migrations.AddField(
                    model_name="subtopic",
                    name="created_at",
                    field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
                ),
                migrations.AddField(
                    model_name="subtopic",
                    name="updated_at",
                    field=models.DateTimeField(auto_now=True, null=True, blank=True),
                ),
            ],
            database_operations=[],
        ),

        # Safe alters (ok bisan existing na ang mga columns)
        migrations.AlterField(
            model_name="topic",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="topic",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="subtopic",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="subtopic",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="readingmaterial",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
        ),
        migrations.AlterField(
            model_name="readingmaterial",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, null=True, blank=True),
        ),
    ]
