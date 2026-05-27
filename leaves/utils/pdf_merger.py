"""
PDF Merger — Δημιουργία ενοποιημένου PDF αίτησης + συνημμένων

Δομή ενοποιημένου PDF:
  Σελίδα 1:  Η αίτηση άδειας (από pdf_template.html)
  Σελίδα 2:  Λίστα "Συνημμένα Αρχεία" με αρίθμηση, όνομα, περιγραφή
  Σελίδα 3+: Κάθε συνημμένο σε δική του σελίδα
"""
import os
import base64
from io import BytesIO

from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from weasyprint import HTML
from pypdf import PdfWriter

from leaves.crypto_utils import SecureFileHandler


def image_to_pdf_bytes(image_bytes, filename_hint=''):
    """
    Μετατρέπει bytes εικόνας (JPG/PNG) σε PDF bytes (μία σελίδα).
    Χρησιμοποιεί WeasyPrint με base64 embedded <img>.
    """
    mime = 'image/png'
    if filename_hint.lower().endswith('.jpg') or filename_hint.lower().endswith('.jpeg'):
        mime = 'image/jpeg'
    b64 = base64.b64encode(image_bytes).decode('ascii')
    html = (
        '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
        '@page { size: A4; margin: 1cm; }'
        'body { margin: 0; padding: 0; text-align: center; }'
        'img { max-width: 100%; max-height: 100%; }'
        '</style></head><body>'
        f'<img src="data:{mime};base64,{b64}" alt="attachment"/>'
        '</body></html>'
    )
    return HTML(string=html).write_pdf()


def build_attachments_index_pdf(attachments_list):
    """
    Δημιουργεί PDF με τη σελίδα ευρετηρίου συνημμένων.
    attachments_list: list of dicts με 'filename', 'description' keys
    """
    html = render_to_string('leaves/pdf_attachments_index.html', {
        'attachments_list': attachments_list,
    })
    return HTML(string=html).write_pdf()


def build_leave_request_pdf(leave_request):
    """
    Δημιουργεί PDF της ίδιας της αίτησης άδειας.
    """
    from leaves.models import LeavePeriod
    periods = LeavePeriod.objects.filter(leave_request=leave_request).order_by('start_date')
    context = {
        'leave_request': leave_request,
        'user': leave_request.user,
        'periods': periods,
        'attachments': list(leave_request.attachments.all()),
    }
    html = render_to_string('leaves/pdf_template.html', context)
    return HTML(string=html).write_pdf()


def convert_attachment_to_pdf(attachment, handler):
    """
    Αποκρυπτογραφεί ένα συνημμένο και το μετατρέπει σε PDF bytes.
    Επιστρέφει (pdf_bytes, filename, description) ή None σε περίπτωση σφάλματος.
    """
    try:
        ext = attachment.file_extension
        decrypted = handler.load_encrypted_file(attachment.file_path, attachment.encryption_key)
        if decrypted is None:
            return None

        if ext == 'pdf':
            return decrypted
        elif ext in ('jpg', 'jpeg', 'png'):
            return image_to_pdf_bytes(decrypted, attachment.original_filename)
        else:
            # Μη υποστηριζόμενος τύπος
            return None
    except Exception:
        return None


def build_merged_pdf(leave_request):
    """
    Δημιουργεί το ενοποιημένο PDF: αίτηση + ευρετήριο συνημμένων + συνημμένα.
    
    Returns:
        bytes: Το πλήρες ενοποιημένο PDF
    """
    writer = PdfWriter()
    handler = SecureFileHandler()

    # 1. Αίτηση
    leave_pdf = build_leave_request_pdf(leave_request)
    writer.append(BytesIO(leave_pdf))

    # 2. Λίστα συνημμένων (μόνο αν υπάρχουν)
    attachments_qs = list(leave_request.attachments.all().order_by('uploaded_at'))
    if attachments_qs:
        attachments_list = [
            {'filename': att.original_filename, 'description': att.description or ''}
            for att in attachments_qs
        ]
        index_pdf = build_attachments_index_pdf(attachments_list)
        writer.append(BytesIO(index_pdf))

        # 3. Κάθε συνημμένο σε δική του σελίδα
        for att in attachments_qs:
            pdf_bytes = convert_attachment_to_pdf(att, handler)
            if pdf_bytes is not None:
                writer.append(BytesIO(pdf_bytes))
            # Αν αποτύχει, απλά παραλείπουμε το συνημμένο

    # Εξαγωγή
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def save_merged_pdf(leave_request):
    """
    Δημιουργεί και αποθηκεύει κρυπτογραφημένο το ενοποιημένο PDF.
    Ενημερώνει τα merged_pdf_* πεδία στο LeaveRequest.
    
    Returns:
        tuple: (pdf_content_bytes, encrypted_path, key_hex)
    """
    pdf_content = build_merged_pdf(leave_request)

    # Δημιουργία directory
    private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                                 os.path.join(settings.BASE_DIR, 'private_media'))
    pdf_dir = os.path.join(private_media_root, 'merged_pdfs', str(leave_request.id))
    os.makedirs(pdf_dir, exist_ok=True)

    # Όνομα αρχείου
    from leaves.decision_helpers import build_decision_pdf_filename
    from leaves.models import LeaveRequest
    filename = f"merged_{leave_request.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_path = os.path.join(pdf_dir, filename)

    # Κρυπτογράφηση
    handler = SecureFileHandler()
    encrypted_path, encryption_key = handler.save_encrypted_bytes(pdf_content, pdf_path)

    # Ενημέρωση μοντέλου
    leave_request.merged_pdf_path = encrypted_path
    leave_request.merged_pdf_encryption_key = encryption_key
    leave_request.merged_pdf_size = len(pdf_content)
    leave_request.merged_pdf_created_at = timezone.now()
    leave_request.save(update_fields=[
        'merged_pdf_path', 'merged_pdf_encryption_key',
        'merged_pdf_size', 'merged_pdf_created_at',
    ])

    return pdf_content, encrypted_path, encryption_key