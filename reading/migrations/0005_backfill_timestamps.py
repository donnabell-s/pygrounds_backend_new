from django.db import migrations
from django.utils import timezone


def backfill(apps, schema_editor):
    now = timezone.now()

    for model_name in ("Topic", "Subtopic", "ReadingMaterial"):
        Model = apps.get_model("reading", model_name)
        # set created_at if null
        (Model.objects
              .filter(created_at__isnull=True)
              .update(created_at=now))
        # set updated_at if null
        (Model.objects
              .filter(updated_at__isnull=True)
              .update(updated_at=now))


class Migration(migrations.Migration):

    dependencies = [
        ("reading", "0004_merge_0002_0003"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE reading_topic
                    ADD COLUMN IF NOT EXISTS created_at timestamp with time zone,
                    ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone;
                ALTER TABLE reading_subtopic
                    ADD COLUMN IF NOT EXISTS created_at timestamp with time zone,
                    ADD COLUMN IF NOT EXISTS updated_at timestamp with time zone;
            """,
            reverse_sql="""
                ALTER TABLE reading_topic
                    DROP COLUMN IF EXISTS updated_at,
                    DROP COLUMN IF EXISTS created_at;
                ALTER TABLE reading_subtopic
                    DROP COLUMN IF EXISTS updated_at,
                    DROP COLUMN IF EXISTS created_at;
            """,
        ),

        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
