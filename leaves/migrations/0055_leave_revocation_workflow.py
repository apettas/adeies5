# Ανάκληση ολοκληρωμένης άδειας: status + revocation_scope + τύπος LeaveType

from django.db import migrations, models


def ensure_revocation_leave_type(apps, schema_editor):
    LeaveType = apps.get_model('leaves', 'LeaveType')
    existing = LeaveType.objects.filter(is_revocation=True, is_active=True).first()
    if existing:
        return
    LeaveType.objects.get_or_create(
        code='LT_REVOCATION',
        defaults={
            'name': 'Ανάκληση Άδειας',
            'requires_approval': True,
            'is_active': True,
            'is_revocation': True,
            'affects_regular_leave_balance': False,
            'is_simple': False,
            'subject_text': 'Ανάκληση Άδειας',
            'decision_text': 'ανάκληση της κατωτέρω άδειας',
            'instructions': (
                'Η αίτηση ανάκλησης δημιουργείται μόνο από ολοκληρωμένη άδεια.'
            ),
        },
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0054_protocol_email_failure_alert'),
    ]

    operations = [
        migrations.AddField(
            model_name='leaverequest',
            name='revocation_scope',
            field=models.CharField(
                blank=True,
                choices=[('TOTAL', 'Ολική'), ('PARTIAL', 'Μερική')],
                help_text='Ολική ή μερική — μόνο για αιτήσεις τύπου ανάκλησης',
                max_length=10,
                verbose_name='Εύρος Ανάκλησης',
            ),
        ),
        migrations.AlterField(
            model_name='leaverequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('DRAFT', 'Πρόχειρη αίτηση'),
                    ('SUBMITTED', 'Υποβληθείσα αίτηση'),
                    ('PENDING_KEDASY_PROTOCOL', 'Εκκρεμεί Πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ'),
                    ('PENDING_PROTOCOL', 'Για πρωτόκολλο ΠΔΕΔΕ'),
                    ('IN_REVIEW', 'Σε επεξεργασία από τμήμα αδειών'),
                    ('WAITING_FOR_DOCUMENTS', 'Σε αναμονή δικαιολογητικών'),
                    ('DECISION_PREPARATION', 'Ετοιμασία απόφασης'),
                    ('PENDING_YC_COMMITTEE', 'Αναμονή απόφασης Υγειονομικής Επιτροπής'),
                    ('PENDING_SIGNATURES', 'ΣΗΔΕ - προς υπογραφές'),
                    ('COMPLETED', 'Ολοκληρώθηκε'),
                    ('REVOKED_BY_REQUEST', 'ΑΝΑΚΛΗΣΗ ΑΔΕΙΑΣ ΑΠΟ ΑΙΤΗΣΗ'),
                    ('SUPERVISOR_REJECTED', 'Αρνητική έγκριση προϊσταμένου'),
                    ('REJECTED_BY_LEAVES_DEPT', 'Απόρριψη από τμήμα αδειών'),
                    ('CANCELLED_BY_APPLICANT', 'Ανάκληση από αιτούντα'),
                ],
                default='DRAFT',
                max_length=40,
                verbose_name='Κατάσταση',
            ),
        ),
        migrations.RunPython(ensure_revocation_leave_type, noop_reverse),
    ]
