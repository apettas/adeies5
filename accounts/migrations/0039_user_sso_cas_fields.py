from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0038_user_employee_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='gsn_branch',
            field=models.CharField(
                blank=True,
                help_text='Κλάδος από Σχολικό Δίκτυο (gsnBranch)',
                max_length=100,
                verbose_name='Κλάδος (ΠΣΔ)',
            ),
        ),
        migrations.AddField(
            model_name='user',
            name='sso_organizational_unit',
            field=models.CharField(
                blank=True,
                help_text='ou από Σχολικό Δίκτυο — σχολική/υπηρεσιακή μονάδα',
                max_length=255,
                verbose_name='Οργανική Μονάδα (ΠΣΔ)',
            ),
        ),
        migrations.AlterField(
            model_name='user',
            name='role_description',
            field=models.TextField(
                blank=True,
                help_text='Ιδιότητα του χρήστη από ΠΣΔ (title)',
                verbose_name='Υπηρεσιακή Ιδιότητα',
            ),
        ),
    ]
