# Generated manually due to WeasyPrint dependency issues

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('leaves', '0016_alter_leavetype_requires_approval'),
    ]

    operations = [
        migrations.AlterField(
            model_name='leaverequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('DRAFT', 'Προσχέδιο'),
                    ('SUBMITTED', 'Υποβλήθηκε'),
                    ('APPROVED_MANAGER', 'Εγκρίθηκε από Προϊστάμενο'),
                    ('REJECTED_MANAGER', 'Απορρίφθηκε από Προϊστάμενο'),
                    ('PENDING_KEDASY_KEPEA_PROTOCOL', 'Εκκρεμεί Πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ'),
                    ('FOR_PROTOCOL_PDEDE', 'Για Πρωτόκολλο ΠΔΕΔΕ'),
                    ('UNDER_PROCESSING', 'Προς Επεξεργασία'),
                    ('COMPLETED', 'Ολοκληρώθηκε'),
                    ('REJECTED_OPERATOR', 'Απορρίφθηκε από Χειριστή'),
                ],
                default='DRAFT',
                max_length=40,
                verbose_name='Κατάσταση'
            ),
        ),
        migrations.AddField(
            model_name='leaverequest',
            name='kedasy_kepea_protocol_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='kedasy_kepea_protocols',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ από'
            ),
        ),
        migrations.AddField(
            model_name='leaverequest',
            name='kedasy_kepea_protocol_date',
            field=models.DateTimeField(
                blank=True,
                null=True,
                verbose_name='Ημερομηνία Πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ'
            ),
        ),
        migrations.AddField(
            model_name='leaverequest',
            name='kedasy_kepea_protocol_number',
            field=models.CharField(
                blank=True,
                max_length=100,
                verbose_name='Αριθμός Πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ'
            ),
        ),
    ]