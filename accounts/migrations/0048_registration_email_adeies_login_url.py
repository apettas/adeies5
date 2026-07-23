from django.db import migrations


NEW_BODY = """Αγαπητέ/ή {full_name},

Ο λογαριασμός σας στο Σύστημα Διαχείρισης Αδειών της Περιφερειακής Διεύθυνσης Εκπαίδευσης Δυτικής Ελλάδας ενεργοποιήθηκε επιτυχώς.

Μπορείτε πλέον να συνδεθείτε στο σύστημα μέσω ΠΣΔ (Σχολικό Δίκτυο): https://adeies.pdede.gov.gr/login/

Παρακαλούμε να αλλάξετε τον κωδικό πρόσβασής σας με την πρώτη σύνδεση.

Με εκτίμηση,
ΠΔΕ Δυτικής Ελλάδας
Σύστημα Διαχείρισης Αδειών «Αλκίνοος»"""


def set_adeies_login_url(apps, schema_editor):
    RegistrationApprovalEmailTemplate = apps.get_model(
        'accounts', 'RegistrationApprovalEmailTemplate'
    )
    template = RegistrationApprovalEmailTemplate.objects.filter(pk=1).first()
    if not template:
        return
    template.body = NEW_BODY
    template.save(update_fields=['body'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0047_update_registration_approval_login_line'),
    ]

    operations = [
        migrations.RunPython(set_adeies_login_url, noop_reverse),
    ]
