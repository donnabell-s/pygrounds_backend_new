from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    dependencies = [
        ('reading', '0003_topic_readingmaterial_topic_ref'),
    ]

    operations = [
        # 1) Create Subtopic model
        migrations.CreateModel(
            name='Subtopic',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('slug', models.SlugField(blank=True, max_length=255)),
                ('order_in_topic', models.PositiveIntegerField(default=0)),
                ('topic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='subtopics', to='reading.topic')),
            ],
            options={'ordering': ['topic__name', 'order_in_topic', 'name']},
        ),

        
        migrations.AddField(
            model_name='readingmaterial',
            name='subtopic_ref',
            field=models.ForeignKey(
                to='reading.subtopic',
                on_delete=django.db.models.deletion.CASCADE,
                related_name='materials',
                null=True, blank=True,
            ),
        ),
    ]
