"""
Alerts για ανέβασμα δικαιολογητικών από αιτούντα — «Έλαβα Γνώση» στο dashboard χειριστή.
"""
from leaves.models import DocumentUploadAcknowledgment, LeaveRequest


def get_pending_document_upload_alerts(handler):
    """
    Αιτήσεις σε αναμονή δικαιολογητικών όπου ο αιτών έχει ανεβάσει αρχείο
    και ο χειριστής δεν έχει δηλώσει «Έλαβα Γνώση».
    """
    acknowledged_ids = DocumentUploadAcknowledgment.objects.filter(
        handler=handler,
    ).values_list('leave_request_id', flat=True)

    return LeaveRequest.objects.filter(
        status='WAITING_FOR_DOCUMENTS',
        applicant_documents_uploaded_at__isnull=False,
    ).exclude(
        id__in=acknowledged_ids,
    ).select_related('user', 'user__department', 'leave_type').order_by(
        '-applicant_documents_uploaded_at',
    )


def mark_applicant_document_uploaded(leave_request):
    """Καταγραφή ανεβάσματος από αιτούντα — επαναφορά alerts για όλους τους χειριστές."""
    from django.utils import timezone

    leave_request.applicant_documents_uploaded_at = timezone.now()
    leave_request.save(update_fields=['applicant_documents_uploaded_at'])
    DocumentUploadAcknowledgment.objects.filter(leave_request=leave_request).delete()
