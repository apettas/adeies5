"""
Email utilities — αποστολή ενοποιημένου PDF μέσω email
"""
from django.core.mail import EmailMessage, send_mail
from django.conf import settings
from django.utils import timezone


def send_registration_approved_email(user):
    """
    Στέλνει email ειδοποίησης στον χρήστη ότι ο λογαριασμός του ενεργοποιήθηκε.
    
    Args:
        user: User instance που μόλις εγκρίθηκε
    
    Returns:
        bool: True αν στάλθηκε επιτυχώς
    """
    subject = 'Ενεργοποίηση Λογαριασμού - Σύστημα Διαχείρισης Αδειών ΠΔΕΔΕ'
    message = (
        f"Αγαπητέ/ή {user.full_name},\n\n"
        f"Ο λογαριασμός σας στο Σύστημα Διαχείρισης Αδειών της "
        f"Περιφερειακής Διεύθυνσης Εκπαίδευσης Δυτικής Ελλάδας ενεργοποιήθηκε επιτυχώς.\n\n"
        f"Μπορείτε πλέον να συνδεθείτε στο σύστημα:\n"
        f"  - Μέσω ΠΣΔ (Σχολικό Δίκτυο): {settings.LOGIN_URL}\n"
        f"  - Μέσω email και κωδικού: {settings.LOGIN_URL}\n\n"
        f"Παρακαλούμε να αλλάξετε τον κωδικό πρόσβασής σας με την πρώτη σύνδεση.\n\n"
        f"Με εκτίμηση,\n"
        f"ΠΔΕ Δυτικής Ελλάδας\n"
        f"Σύστημα Διαχείρισης Αδειών «Αλκίνοος»"
    )
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send approval email to {user.email}: {e}")
        return False


def send_registration_approved_notification(user):
    """
    Δημιουργεί ειδοποίηση εντός συστήματος για τον χρήστη.
    
    Args:
        user: User instance που μόλις εγκρίθηκε
    
    Returns:
        Notification instance or None
    """
    try:
        from notifications.utils import create_notification
        return create_notification(
            user=user,
            title='Ο λογαριασμός σας ενεργοποιήθηκε',
            message=(
                f'Ο λογαριασμός σας στο Σύστημα Διαχείρισης Αδειών ενεργοποιήθηκε. '
                f'Μπορείτε πλέον να συνδεθείτε και να υποβάλετε αιτήσεις άδειας.'
            ),
            notification_type='success'
        )
    except Exception:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Could not create notification for approved user {user.email}")
        return None


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


def send_merged_pdf_email(leave_request, pdf_bytes, recipient=None, custom_subject=None):
    """
    Στέλνει το ενοποιημένο PDF μέσω email.

    Args:
        leave_request: LeaveRequest instance
        pdf_bytes: bytes του ενοποιημένου PDF
        recipient: (optional) email παραλήπτη. Αν δεν δοθεί, χρησιμοποιείται το PROTOCOL_EMAIL_RECIPIENT από settings.
        custom_subject: (optional) προσαρμοσμένο θέμα email. Αν δεν δοθεί, χρησιμοποιείται το default.

    Returns:
        bool: True αν στάλθηκε επιτυχώς
    """
    if recipient is None:
        recipient = getattr(settings, 'PROTOCOL_EMAIL_RECIPIENT', 'apettas@gmail.com')

    subject = custom_subject if custom_subject else build_email_subject(leave_request)
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


def send_documents_required_email(leave_request, recipient_email, upload_url=''):
    """
    Email στον αιτούντα όταν απαιτούνται δικαιολογητικά.

    Returns:
        bool: True αν στάλθηκε επιτυχώς
    """
    if not recipient_email:
        return False

    deadline_text = ''
    if leave_request.documents_deadline:
        deadline_text = leave_request.documents_deadline.strftime('%d/%m/%Y %H:%M')

    message_lines = [
        f"Αγαπητέ/ή {leave_request.user.full_name},",
        "",
        "Για την αίτησή σας άδειας στο Σύστημα Διαχείρισης Αδειών «Αλκίνοος» "
        "απαιτούνται επιπλέον δικαιολογητικά.",
        "",
        f"Αρ. Αίτησης: #{leave_request.pk}",
        f"Τύπος Άδειας: {leave_request.leave_type.name}",
        "Απαιτούμενα Δικαιολογητικά:",
        leave_request.required_documents,
    ]
    if deadline_text:
        message_lines.extend(["", f"Προθεσμία κατάθεσης: {deadline_text}"])
    if upload_url:
        message_lines.extend([
            "",
            "Μπορείτε να συνδεθείτε στο σύστημα και να ανεβάσετε τα δικαιολογητικά εδώ:",
            upload_url,
        ])
    message_lines.extend([
        "",
        "Με εκτίμηση,",
        "ΠΔΕ Δυτικής Ελλάδας",
        "Σύστημα Διαχείρισης Αδειών «Αλκίνοος»",
    ])

    try:
        send_mail(
            subject=(
                f"Απαιτούνται Δικαιολογητικά — Αίτηση #{leave_request.pk} "
                f"({leave_request.leave_type.name})"
            ),
            message="\n".join(message_lines),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(
            "Failed to send documents-required email for leave request %s to %s: %s",
            leave_request.id,
            recipient_email,
            e,
        )
        return False