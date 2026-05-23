import re

from django.utils import timezone


def build_decision_pdf_filename(leave_request, reference_date=None):
    """
    Όνομα αρχείου απόφασης: yyyymmdd_Username_leavetype_Αποφαση.pdf
    Username = τοπικό μέρος email (πριν το @).
    leavetype = κωδικός τύπου άδειας ή το όνομά του.
    """
    ref = reference_date or leave_request.decision_created_at or timezone.now()
    date_str = ref.strftime('%Y%m%d')

    user = leave_request.user
    username = (user.email.split('@')[0] if user.email else 'user').strip()
    username = re.sub(r'[^\w\-]', '', username, flags=re.UNICODE) or 'user'

    leave_type = leave_request.leave_type
    lt = (leave_type.code or leave_type.name).strip()
    lt = re.sub(r'[\s/\\]+', '_', lt)
    lt = re.sub(r'[^\w\-]', '', lt, flags=re.UNICODE) or 'adidia'

    return f'{date_str}_{username}_{lt}_Αποφαση.pdf'
