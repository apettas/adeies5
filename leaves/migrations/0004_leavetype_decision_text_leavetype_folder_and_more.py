# Generated by Django 5.2.3 on 2025-06-29 09:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0003_remove_leaverequest_end_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='leavetype',
            name='decision_text',
            field=models.TextField(blank=True, verbose_name='Κείμενο Απόφασης'),
        ),
        migrations.AddField(
            model_name='leavetype',
            name='folder',
            field=models.CharField(blank=True, max_length=255, verbose_name='Φ Φάκελος'),
        ),
        migrations.AddField(
            model_name='leavetype',
            name='general_category',
            field=models.CharField(blank=True, max_length=100, verbose_name='Γενική Κατηγορία Αδειών'),
        ),
        migrations.AddField(
            model_name='leavetype',
            name='subject_text',
            field=models.TextField(blank=True, verbose_name='Κείμενο Θέματος'),
        ),
    ]
