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
    subject = f'[PDEDE Leaves] Κλείδωμα login — {username or "άγνωστο"}'
    message = (
        f'Ανιχνεύθηκαν πολλαπλές αποτυχημένες προσπάθειες σύνδεσης.\n\n'
        f'Username/email: {username or "—"}\n'
        f'IP: {ip_address or "—"}\n'
        f'User-Agent: {user_agent}\n\n'
        f'Το django-axes έχει κλειδώσει προσωρινά την πρόσβαση.\n'
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
