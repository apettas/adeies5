from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('leaves', '0049_documents_notification_and_upload_alerts'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='applicant_documents_submitted_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Ημερομηνία Ολοκλήρωσης Αποστολής Δικαιολογητικών από Αιτούντα',
            ),
        ),
        migrations.CreateModel(
            name='ApplicantDocumentsSubmissionAcknowledgment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('acknowledged_at', models.DateTimeField(auto_now_add=True, verbose_name='Ημερομηνία Γνώσης')),
                (
                    'handler',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='document_submission_acknowledgments',
                        to=settings.AUTH_USER_MODEL,
                        verbose_name='Χειριστής',
                    ),
                ),
                (
                    'leave_request',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='document_submission_acknowledgments',
                        to='leaves.leaverequest',
                        verbose_name='Αίτηση Άδειας',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Γνώση Ολοκλήρωσης Αποστολής Δικαιολογητικών',
                'verbose_name_plural': 'Γνώσεις Ολοκλήρωσης Αποστολής Δικαιολογητικών',
                'ordering': ['-acknowledged_at'],
                'unique_together': {('leave_request', 'handler')},
            },
        ),
    ]
