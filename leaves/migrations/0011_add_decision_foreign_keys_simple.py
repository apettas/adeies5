# Generated manually to add missing foreign key fields

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0010_add_missing_decision_foreign_keys'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='decision_logo',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='leaves.logo',
                verbose_name='Λογότυπο Απόφασης'
            ),
        ),
        migrations.AddField(
            model_name='leaverequest',
            name='decision_info',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='leaves.info',
                verbose_name='Πληροφορίες Απόφασης'
            ),
        ),
        migrations.AddField(
            model_name='leaverequest',
            name='decision_ypopsin',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='leaves.ypopsin',
                verbose_name='Υπογραφή Απόφασης'
            ),
        ),
        migrations.AddField(
            model_name='leaverequest',
            name='decision_signee',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to='leaves.signee',
                verbose_name='Υπογράφων Απόφασης'
            ),
        ),
    ]