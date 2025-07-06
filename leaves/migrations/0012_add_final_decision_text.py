# Generated manually to add missing final_decision_text field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0011_add_decision_foreign_keys_simple'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='final_decision_text',
            field=models.TextField(
                blank=True,
                null=True,
                verbose_name='Τελικό Κείμενο Απόφασης'
            ),
        ),
    ]