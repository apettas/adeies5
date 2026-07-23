"""
Alerts για αποτυχία αυτόματης αποστολής email πρωτοκόλλου — «Έλαβα Γνώση».
"""
from django.utils import timezone

from leaves.models import LeaveRequest, ProtocolEmailFailureAcknowledgment


def mark_protocol_email_failed(leave_request):
    """Καταγραφή αποτυχίας — επαναφορά acknowledgments για όλους τους χειριστές."""
    leave_request.protocol_email_failed_at = timezone.now()
    leave_request.save(update_fields=['protocol_email_failed_at'])
    ProtocolEmailFailureAcknowledgment.objects.filter(leave_request=leave_request).delete()


def clear_protocol_email_failure(leave_request):
    """Επιτυχής αποστολή — καθαρισμός alert."""
    if leave_request.protocol_email_failed_at is None:
        return
    leave_request.protocol_email_failed_at = None
    leave_request.save(update_fields=['protocol_email_failed_at'])
    ProtocolEmailFailureAcknowledgment.objects.filter(leave_request=leave_request).delete()


def get_pending_protocol_email_failure_alerts(handler):
    """
    Αιτήσεις με αποτυχημένη αυτόματη αποστολή email πρωτοκόλλου
    που ο χειριστής δεν έχει δηλώσει «Έλαβα Γνώση».
    """
    acknowledged_ids = ProtocolEmailFailureAcknowledgment.objects.filter(
        handler=handler,
    ).values_list('leave_request_id', flat=True)

    return LeaveRequest.objects.filter(
        protocol_email_failed_at__isnull=False,
    ).exclude(
        id__in=acknowledged_ids,
    ).select_related('user', 'user__department', 'leave_type').order_by(
        '-protocol_email_failed_at',
    )
