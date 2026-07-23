from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver


@receiver(user_logged_in)
def notify_substitute_reappearance(sender, request, user, **kwargs):
    """Ειδοποίηση χειριστών όταν αναπληρωτής σε αναμονή κάνει login."""
    try:
        from leaves.utils.substitute_contracts import maybe_notify_handlers_on_reappearance
        maybe_notify_handlers_on_reappearance(user)
    except Exception:
        # Μην μπλοκάρουμε το login για αποτυχία ειδοποίησης
        pass
