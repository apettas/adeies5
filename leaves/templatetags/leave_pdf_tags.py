"""Βοηθητικά για το κείμενο σώματος PDF αίτησης."""

from django import template

register = template.Library()


def build_default_request_body_text(leave_request):
    leave_type = leave_request.leave_type
    phrase = (leave_type.decision_text or leave_type.name or '').strip()
    return f'Παρακαλώ να μου χορηγήσετε {phrase} για τα κάτωθι χρονικά διαστήματα:'


def _legacy_auto_request_body_text(leave_request):
    leave_type = leave_request.leave_type
    return (
        f'Παρακαλώ να μου χορηγήσετε άδεια {leave_type.name} '
        f'για τα κάτωθι χρονικά διαστήματα:'
    )


def resolve_request_body_text(leave_request, override_text=''):
    """Επιστρέφει το κείμενο αίτησης, αγνοώντας παλιά αυτόματα templates."""
    override_text = (override_text or '').strip()
    default_text = build_default_request_body_text(leave_request)
    if not override_text:
        return default_text
    if override_text in (default_text, _legacy_auto_request_body_text(leave_request)):
        return default_text
    return override_text


@register.filter
def leave_request_body_text(leave_request, override_text=''):
    return resolve_request_body_text(leave_request, override_text)
