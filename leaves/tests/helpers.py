"""Βοηθητικά utilities για tests αιτήσεων άδειας."""
from django.urls import reverse
from django.utils import timezone

from leaves.models import LeavePeriod, LeaveRequest


def create_draft_leave_request(user, leave_type, description, start_date, end_date):
    """Δημιουργεί πρόχειρη αίτηση με ένα διάστημα."""
    leave_request = LeaveRequest.objects.create(
        user=user,
        leave_type=leave_type,
        description=description,
        status='DRAFT',
    )
    LeavePeriod.objects.create(
        leave_request=leave_request,
        start_date=start_date,
        end_date=end_date,
    )
    return leave_request


def create_submitted_leave_request(user, leave_type, description, start_date, end_date):
    """Δημιουργεί υποβληθείσα αίτηση με ένα διάστημα."""
    leave_request = LeaveRequest.objects.create(
        user=user,
        leave_type=leave_type,
        description=description,
        status='SUBMITTED',
        submitted_at=timezone.now(),
    )
    LeavePeriod.objects.create(
        leave_request=leave_request,
        start_date=start_date,
        end_date=end_date,
    )
    return leave_request


def submit_leave_request(leave_request):
    """Υποβολή πρόχειρης αίτησης μέσω model."""
    assert leave_request.submit(), 'Η υποβολή απέτυχε'
    leave_request.refresh_from_db()
    return leave_request


def approve_leave_as_manager(client, leave_request, comments=''):
    """Έγκριση από προϊστάμενο μέσω view."""
    return client.post(
        reverse('leaves:approve_leave_request', kwargs={'pk': leave_request.pk}),
        {'comments': comments},
    )


def add_kedasy_protocol(client, leave_request, protocol_number='KED-001', protocol_date='2025-01-10'):
    """Πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ μέσω view."""
    return client.post(
        reverse('leaves:add_kedasy_kepea_protocol', kwargs={'pk': leave_request.pk}),
        {
            'protocol_number': protocol_number,
            'protocol_date': protocol_date,
            'comments': '',
        },
    )


def send_pdede_protocol(client, leave_request, protocol_number='PDEDE-001', protocol_date='2025-01-12'):
    """Αποστολή σε πρωτόκολλο ΠΔΕΔΕ → IN_REVIEW."""
    return client.post(
        reverse('leaves:send_to_protocol_pdede', kwargs={'pk': leave_request.pk}),
        {
            'protocol_number': protocol_number,
            'protocol_date': protocol_date,
            'protocol_details': '',
        },
    )


def advance_leave_to_in_review(client, leave_request, protocol_number='PDEDE-001', protocol_date='2025-01-12'):
    """Μεταφορά αίτησης από PENDING_PROTOCOL σε IN_REVIEW."""
    response = send_pdede_protocol(client, leave_request, protocol_number, protocol_date)
    leave_request.refresh_from_db()
    return response


def reject_leave_as_handler(client, leave_request, reason='Απόρριψη test'):
    """Απόρριψη από χειριστή μέσω view."""
    return client.post(
        reverse('leaves:reject_leave_request_by_handler', kwargs={'pk': leave_request.pk}),
        {'reason': reason},
    )


def complete_leave_as_handler(client, leave_request, balance_after=19, comments='Test completion'):
    """Ολοκληρώνει αίτηση σε IN_REVIEW μέσω handler view."""
    return client.post(
        reverse('leaves:complete_leave_request', kwargs={'pk': leave_request.pk}),
        {
            'balance_after': balance_after,
            'comments': comments,
        },
    )
