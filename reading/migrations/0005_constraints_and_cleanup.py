from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('reading', '0004_create_subtopic_and_fk'),
    ]

    operations = [
        # 1) Make subtopic_ref REQUIRED now that backfill is done
        migrations.AlterField(
            model_name='readingmaterial',
            name='subtopic_ref',
            field=models.ForeignKey(
                to='reading.subtopic',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='materials',
                null=False, blank=False,
            ),
        ),

        # 2) Add unique constraints
        migrations.AddConstraint(
            model_name='subtopic',
            constraint=models.UniqueConstraint(
                fields=('topic', 'name'),
                name='uniq_topic_subtopic',
            ),
        ),
        migrations.AddConstraint(
            model_name='readingmaterial',
            constraint=models.UniqueConstraint(
                fields=('topic_ref', 'subtopic_ref', 'title'),
                name='uniq_topic_subtopic_title',
            ),
        ),

        # 3) Remove legacy string fields from ReadingMaterial
        migrations.RemoveField(model_name='readingmaterial', name='topic'),
        migrations.RemoveField(model_name='readingmaterial', name='subtopic'),
    ]
