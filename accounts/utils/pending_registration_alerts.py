"""
Alerts για νέες εγγραφές χρηστών — «Έλαβα Γνώση» στο dashboard χειριστή.
"""
from django.utils import timezone

from accounts.models import PendingRegistrationAcknowledgment, User


def get_pending_registrations_queryset():
    """Όλες οι εκκρεμείς εγγραφές με υποβληθέντα στοιχεία."""
    return User.objects.filter(
        registration_status='PENDING',
        registration_submitted_at__isnull=False,
    ).select_related(
        'department',
        'specialty',
        'employee_type',
    ).order_by('-registration_submitted_at')


def get_pending_registration_alerts(handler):
    """
    Εκκρεμείς εγγραφές που ο χειριστής δεν έχει δηλώσει «Έλαβα Γνώση».
    """
    acknowledged_ids = PendingRegistrationAcknowledgment.objects.filter(
        handler=handler,
    ).values_list('pending_user_id', flat=True)

    return get_pending_registrations_queryset().exclude(id__in=acknowledged_ids)


def mark_registration_submitted(user):
    """
    Καταγραφή υποβολής στοιχείων εγγραφής — επαναφορά alerts για όλους τους χειριστές.
    """
    user.registration_submitted_at = timezone.now()
    user.save(update_fields=['registration_submitted_at'])
    PendingRegistrationAcknowledgment.objects.filter(pending_user=user).delete()
