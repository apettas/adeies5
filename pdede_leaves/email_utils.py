"""
Email utilities — αποστολή ενοποιημένου PDF μέσω email
"""
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone


def build_email_subject(leave_request):
    """
    Δημιουργεί το θέμα του email με format:
    Ονοματεπώνυμο αιτούντα - Τύπος άδειας - email αιτούντα - Αρ.Πρωτ.ΚΕΔΑΣΥ (αν υπάρχει)
    """
    parts = [
        leave_request.user.full_name,
        leave_request.leave_type.name,
        leave_request.user.email,
    ]
    if leave_request.kedasy_kepea_protocol_number:
        parts.append(leave_request.kedasy_kepea_protocol_number)
    return ' - '.join(parts)


def send_merged_pdf_email(leave_request, pdf_bytes):
    """
    Στέλνει το ενοποιημένο PDF μέσω email.
    
    Args:
        leave_request: LeaveRequest instance
        pdf_bytes: bytes του ενοποιημένου PDF
    
    Returns:
        bool: True αν στάλθηκε επιτυχώς
    """
    recipient = getattr(settings, 'PROTOCOL_EMAIL_RECIPIENT', 'apettas@gmail.com')
    
    subject = build_email_subject(leave_request)
    body = (
        f"Αποστολή αίτησης άδειας για πρωτόκολλο.\n\n"
        f"Αιτών/Αιτούσα: {leave_request.user.full_name}\n"
        f"Email: {leave_request.user.email}\n"
        f"Τύπος Άδειας: {leave_request.leave_type.name}\n"
        f"Διάρκεια: {leave_request.total_days} ημέρες\n"
        f"Ημερομηνίες: {leave_request.start_date} - {leave_request.end_date}\n"
    )
    if leave_request.kedasy_kepea_protocol_number:
        body += f"Αριθμός Πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ: {leave_request.kedasy_kepea_protocol_number}\n"
    body += f"\nΤο ενοποιημένο PDF επισυνάπτεται.\n"
    
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
    )
    
    # Επισύναψη PDF
    pdf_filename = f"merged_{leave_request.id}_{leave_request.user.full_name.replace(' ', '_')}.pdf"
    email.attach(pdf_filename, pdf_bytes, 'application/pdf')
    
    try:
        email.send()
        leave_request.merged_pdf_sent_at = timezone.now()
        leave_request.save(update_fields=['merged_pdf_sent_at'])
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send email for leave request {leave_request.id}: {e}")
        return False