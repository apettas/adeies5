import re

from django.db import migrations


def remove_alt_login_line(apps, schema_editor):
    RegistrationApprovalEmailTemplate = apps.get_model(
        'accounts', 'RegistrationApprovalEmailTemplate'
    )
    template = RegistrationApprovalEmailTemplate.objects.filter(pk=1).first()
    if not template or not template.body:
        return

    body = template.body
    cleaned = re.sub(
        r'\n[ \t]*-[ \t]*Μέσω email και κωδικού:[^\n]*',
        '',
        body,
        flags=re.IGNORECASE,
    )
    # Αφαίρεση τυχόν κειμένου που κόλλησε μετά την πρόταση αλλαγής κωδικού
    cleaned = re.sub(
        r'(Παρακαλούμε να αλλάξετε τον κωδικό πρόσβασής σας με την πρώτη σύνδεση\.)[ \t]+\S+',
        r'\1',
        cleaned,
    )
    cleaned = cleaned.strip()
    if cleaned and cleaned != body.strip():
        template.body = cleaned
        template.save(update_fields=['body'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0042_registration_approval_email_template'),
    ]

    operations = [
        migrations.RunPython(remove_alt_login_line, noop_reverse),
    ]
