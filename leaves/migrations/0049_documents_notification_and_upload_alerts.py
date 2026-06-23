from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('leaves', '0048_backfill_submitted_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='applicant_documents_uploaded_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Ημερομηνία Ανεβάσματος Δικαιολογητικών από Αιτούντα',
            ),
        ),
        migrations.AddField(
            model_name='leaverequest',
            name='documents_notification_email',
            field=models.EmailField(
                blank=True,
                help_text='Email για ειδοποίηση αιτήματος δικαιολογητικών (επεξεργάσιμο από χειριστή)',
                max_length=254,
                verbose_name='Email Ειδοποίησης Δικαιολογητικών',
            ),
        ),
        migrations.CreateModel(
            name='DocumentUploadAcknowledgment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acknowledged_at', models.DateTimeField(auto_now_add=True, verbose_name='Ημερομηνία Γνώσης')),
                (
                    'handler',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='document_upload_acknowledgments',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Χειριστής',
                    ),
                ),
                (
                    'leave_request',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='document_upload_acknowledgments',
                        to='leaves.leaverequest',
                        verbose_name='Αίτηση Άδειας',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Γνώση Ανεβάσματος Δικαιολογητικών',
                'verbose_name_plural': 'Γνώσεις Ανεβασμάτων Δικαιολογητικών',
                'ordering': ['-acknowledged_at'],
                'unique_together': {('leave_request', 'handler')},
            },
        ),
    ]
