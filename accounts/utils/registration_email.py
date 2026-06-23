"""
Πρότυπο email ενεργοποίησης λογαριασμού μετά από έγκριση εγγραφής.
"""
from django.conf import settings

DEFAULT_REGISTRATION_APPROVAL_SUBJECT = (
    'Ενεργοποίηση Λογαριασμού - Σύστημα Διαχείρισης Αδειών ΠΔΕΔΕ'
)

DEFAULT_REGISTRATION_APPROVAL_BODY = """Αγαπητέ/ή {full_name},

Ο λογαριασμός σας στο Σύστημα Διαχείρισης Αδειών της Περιφερειακής Διεύθυνσης Εκπαίδευσης Δυτικής Ελλάδας ενεργοποιήθηκε επιτυχώς.

Μπορείτε πλέον να συνδεθείτε στο σύστημα:
  - Μέσω ΠΣΔ (Σχολικό Δίκτυο): {login_psd_url}
  - Μέσω email και κωδικού: {login_alt_url}

Παρακαλούμε να αλλάξετε τον κωδικό πρόσβασής σας με την πρώτη σύνδεση.

Με εκτίμηση,
ΠΔΕ Δυτικής Ελλάδας
Σύστημα Διαχείρισης Αδειών «Αλκίνοος»"""

REGISTRATION_EMAIL_PLACEHOLDERS = (
    ('{full_name}', 'Ονοματεπώνυμο χρήστη'),
    ('{email}', 'Email χρήστη'),
    ('{login_psd_url}', 'Σύνδεσμος σύνδεσης μέσω ΠΣΔ'),
    ('{login_alt_url}', 'Σύνδεσμος σύνδεσης με email/κωδικό'),
)


def _login_urls_for_email():
    """Πλήρεις ή σχετικές διευθύνσεις σύνδεσης για το email."""
    base = getattr(settings, 'CAS_ROOT_PROXIED_AS', '').rstrip('/')
    if base:
        return f'{base}/login/', f'{base}/alt/'
    return settings.LOGIN_URL, '/alt/'


def get_registration_approval_email_template():
    from accounts.models import RegistrationApprovalEmailTemplate

    template, _created = RegistrationApprovalEmailTemplate.objects.get_or_create(
        pk=1,
        defaults={
            'subject': DEFAULT_REGISTRATION_APPROVAL_SUBJECT,
            'body': DEFAULT_REGISTRATION_APPROVAL_BODY,
        },
    )
    return template


def _apply_placeholders(text, context):
    rendered = text
    for key, value in context.items():
        rendered = rendered.replace(f'{{{key}}}', value or '')
    return rendered


def build_registration_approval_email(user, template=None):
    """Επιστρέφει (subject, message) για email ενεργοποίησης."""
    if template is None:
        template = get_registration_approval_email_template()

    login_psd_url, login_alt_url = _login_urls_for_email()
    context = {
        'full_name': user.full_name,
        'email': user.email,
        'login_psd_url': login_psd_url,
        'login_alt_url': login_alt_url,
    }
    subject = _apply_placeholders(template.subject, context)
    message = _apply_placeholders(template.body, context)
    return subject, message
