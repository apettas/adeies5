from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0040_remove_user_hire_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='registration_submitted_at',
            field=models.DateTimeField(
                blank=True,
                help_text='Πότε ο χρήστης ολοκλήρωσε τη φόρμα εγγραφής (SSO ή κλασική)',
                null=True,
                verbose_name='Ημερομηνία Υποβολής Στοιχείων',
            ),
        ),
        migrations.CreateModel(
            name='PendingRegistrationAcknowledgment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acknowledged_at', models.DateTimeField(auto_now_add=True, verbose_name='Ημερομηνία Γνώσης')),
                (
                    'handler',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='pending_registration_acknowledgments',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Χειριστής',
                    ),
                ),
                (
                    'pending_user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='registration_acknowledged_by',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Εκκρεμής Χρήστης',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Γνώση Νέας Εγγραφής',
                'verbose_name_plural': 'Γνώσεις Νέων Εγγραφών',
                'ordering': ['-acknowledged_at'],
                'unique_together': {('handler', 'pending_user')},
            },
        ),
    ]
