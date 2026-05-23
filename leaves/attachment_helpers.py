import os
import logging

from django.conf import settings
from django.utils import timezone

from .crypto_utils import SecureFileHandler
from .models import SecureFile

logger = logging.getLogger(__name__)


def save_leave_request_attachments_from_request(request, leave_request, uploaded_by):
    """
    Αποθηκεύει attachment_* από multipart request ως SecureFile.
    Επιστρέφει (saved_count, error_messages).
    """
    errors = []
    pending = []

    for key in sorted(request.FILES.keys()):
        if not key.startswith('attachment_'):
            continue
        file_obj = request.FILES[key]
        if not file_obj:
            continue

        index = key.replace('attachment_', '')
        description = request.POST.get(f'attachment_description_{index}', '').strip()
        if not description:
            errors.append(f'Απαιτείται περιγραφή για το αρχείο «{file_obj.name}».')
            continue

        is_valid, error_message = SecureFileHandler.validate_file(file_obj)
        if not is_valid:
            errors.append(f'Αρχείο «{file_obj.name}»: {error_message}')
            continue

        pending.append((file_obj, description))

    if errors:
        return 0, errors

    private_media_root = getattr(
        settings,
        'PRIVATE_MEDIA_ROOT',
        os.path.join(settings.BASE_DIR, 'private_media'),
    )
    saved = 0

    for file_obj, description in pending:
        try:
            file_path = os.path.join(
                private_media_root,
                'leave_requests',
                str(leave_request.id),
                f"{timezone.now().strftime('%Y%m%d_%H%M%S')}_{file_obj.name}",
            )
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            success, key_hex, file_size = SecureFileHandler.save_encrypted_file(
                file_obj, file_path
            )
            if not success:
                errors.append(f'Αποτυχία αποθήκευσης αρχείου «{file_obj.name}».')
                continue

            SecureFile.objects.create(
                leave_request=leave_request,
                original_filename=file_obj.name,
                file_path=file_path,
                file_size=file_size,
                content_type=file_obj.content_type or '',
                encryption_key=key_hex,
                uploaded_by=uploaded_by,
                description=description,
            )
            saved += 1
        except Exception as exc:
            logger.exception('Error saving attachment %s', file_obj.name)
            errors.append(f'Σφάλμα αποθήκευσης «{file_obj.name}»: {exc}')

    return saved, errors
