from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0050_applicant_documents_submission'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='documents_notification_sent_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Ημερομηνία Αποστολής Email Δικαιολογητικών',
            ),
        ),
    ]
