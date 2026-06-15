"""Βοηθητικά utilities για tests αιτήσεων άδειας."""
from django.urls import reverse
from django.utils import timezone

from leaves.models import LeavePeriod, LeaveRequest


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


def complete_leave_as_handler(client, leave_request, balance_after=19, comments='Test completion'):
    """Ολοκληρώνει αίτηση μέσω handler view."""
    return client.post(
        reverse('leaves:complete_leave_request', kwargs={'pk': leave_request.pk}),
        {
            'balance_after': balance_after,
            'comments': comments,
        },
    )
