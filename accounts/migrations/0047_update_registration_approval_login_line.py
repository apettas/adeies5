import re

from django.db import migrations


NEW_LOGIN_BLOCK = (
    'Μπορείτε πλέον να συνδεθείτε στο σύστημα μέσω ΠΣΔ (Σχολικό Δίκτυο): {login_psd_url}'
)

OLD_LOGIN_PATTERNS = [
    re.compile(
        r'Μπορείτε πλέον να συνδεθείτε στο σύστημα:\s*\n\s*-\s*Μέσω ΠΣΔ \(Σχολικό Δίκτυο\):\s*\S+',
        re.IGNORECASE,
    ),
    re.compile(
        r'Μπορείτε πλέον να συνδεθείτε στο σύστημα:\s*\n\s*-\s*Μέσω ΠΣΔ \(Σχολικό Δίκτυο\):\s*\{login_psd_url\}',
        re.IGNORECASE,
    ),
]


def update_registration_email_login_line(apps, schema_editor):
    RegistrationApprovalEmailTemplate = apps.get_model(
        'accounts', 'RegistrationApprovalEmailTemplate'
    )
    template = RegistrationApprovalEmailTemplate.objects.filter(pk=1).first()
    if not template or not template.body:
        return

    body = template.body
    updated = body
    for pattern in OLD_LOGIN_PATTERNS:
        updated = pattern.sub(NEW_LOGIN_BLOCK, updated)

    # Αν υπάρχει hardcoded sadeies URL στο πρότυπο, αντικατάσταση με placeholder
    updated = updated.replace(
        'https://sadeies.pdede.gov.gr/login/',
        '{login_psd_url}',
    )
    # Αν το κείμενο έχει ήδη τη νέα μορφή αλλά με hardcoded URL
    updated = re.sub(
        r'Μπορείτε πλέον να συνδεθείτε στο σύστημα μέσω ΠΣΔ \(Σχολικό Δίκτυο\):\s*https?://\S+',
        NEW_LOGIN_BLOCK,
        updated,
        flags=re.IGNORECASE,
    )

    if updated != body:
        template.body = updated
        template.save(update_fields=['body'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0046_substitute_contracts'),
    ]

    operations = [
        migrations.RunPython(update_registration_email_login_line, noop_reverse),
    ]
