"""
Email ειδοποιήσεις για security events (django-axes lockout).
"""
import logging

from axes.signals import user_locked_out
from django.conf import settings
from django.core.mail import send_mail
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(user_locked_out)
def email_on_login_lockout(sender, request, username, ip_address, **kwargs):
    """Στέλνει email στο ALERT_EMAIL όταν κλειδώνεται IP/username από axes."""
    recipient = getattr(settings, 'ALERT_EMAIL', None)
    if not recipient:
        return

    user_agent = request.META.get('HTTP_USER_AGENT', '-') if request else '-'
    path = '-'
    if request is not None:
        path = getattr(request, 'path', None) or request.META.get('PATH_INFO', '-')

    cooloff = getattr(settings, 'AXES_COOLOFF_TIME', None)
    failure_limit = getattr(settings, 'AXES_FAILURE_LIMIT', None)

    subject = f'[Adeies] Κλείδωμα login — {username or "άγνωστο"} @ {ip_address or "—"}'
    message = (
        'ALERT: Κλείδωμα σύνδεσης (django-axes)\n'
        '=====================================\n\n'
        'Τι συνέβη\n'
        '---------\n'
        'Υπήρξαν πολλαπλές αποτυχημένες προσπάθειες login και το σύστημα '
        'κλείδωσε προσωρινά την πρόσβαση για αυτό το username και/ή IP.\n\n'
        f'Username/email: {username or "—"}\n'
        f'IP: {ip_address or "—"}\n'
        f'Διαδρομή: {path}\n'
        f'User-Agent: {user_agent}\n'
        f'Όριο αποτυχιών: {failure_limit or "—"}\n'
        f'Διάρκεια κλειδώματος (cooloff): {cooloff or "—"}\n\n'
        'Γιατί ενεργοποιήθηκε\n'
        '--------------------\n'
        'Προστασία από brute-force / credential stuffing στο /alt ή σε '
        'άλλη φόρμα password login. Μπορεί να είναι επίθεση ή ξεχασμένος '
        'κωδικός από νόμιμο χρήστη.\n\n'
        'Τι να κάνεις\n'
        '------------\n'
        '1. Αν είναι γνωστός χρήστης: περίμενε το cooloff ή ξεκλείδωσε από '
        'Django admin (Axes) / manage.py axes_reset.\n'
        '2. Αν η IP είναι άγνωστη/ύποπτη: έλεγξε Cloudflare Security Events, '
        'ενίσχυσε rate limit στο /alt, θεώρησε Cloudflare Access για /alt.\n'
        '3. Αν επαναλαμβάνεται από πολλές IPs: ενεργοποίησε/τσίτα Bot Fight '
        'και Leaked Credentials στο Cloudflare.\n'
        '4. Μην ξεκλειδώνεις μαζικά χωρίς έλεγχο — μπορεί να διευκολύνεις επίθεση.\n\n'
        'Host: adeies.pdede.gov.gr (Adeies / ΠΔΕΔΕ)\n'
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Αποτυχία αποστολής security alert email για axes lockout')
