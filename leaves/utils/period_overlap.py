"""Έλεγχος επικάλυψης διαστημάτων άδειας με υπάρχουσες αιτήσεις του ίδιου χρήστη."""

from leaves.models import LeavePeriod

# Καταστάσεις που θεωρούνται ενεργές για προειδοποίηση επικάλυψης
OVERLAP_RELEVANT_STATUSES = (
    'DRAFT',
    'SUBMITTED',
    'PENDING_KEDASY_PROTOCOL',
    'PENDING_PROTOCOL',
    'IN_REVIEW',
    'WAITING_FOR_DOCUMENTS',
    'DECISION_PREPARATION',
    'PENDING_YC_COMMITTEE',
    'PENDING_SIGNATURES',
    'COMPLETED',
)


def serialize_user_leave_periods_for_overlap(user, exclude_request_id=None):
    """
    Επιστρέφει λίστα αιτήσεων με διαστήματα για client-side έλεγχο επικάλυψης.

    [
      {
        "id": 12,
        "leave_type": "Κανονική",
        "status": "Υποβληθείσα αίτηση",
        "periods": [{"start": "2026-07-01", "end": "2026-07-10"}, ...]
      },
      ...
    ]
    """
    if not user or not getattr(user, 'pk', None):
        return []

    qs = (
        LeavePeriod.objects.filter(
            leave_request__user=user,
            leave_request__status__in=OVERLAP_RELEVANT_STATUSES,
        )
        .select_related('leave_request', 'leave_request__leave_type')
        .order_by('leave_request_id', 'start_date')
    )
    if exclude_request_id:
        qs = qs.exclude(leave_request_id=exclude_request_id)

    by_request = {}
    for period in qs:
        lr = period.leave_request
        entry = by_request.get(lr.id)
        if entry is None:
            entry = {
                'id': lr.id,
                'leave_type': lr.leave_type.name if lr.leave_type_id else '',
                'status': lr.get_status_display(),
                'periods': [],
            }
            by_request[lr.id] = entry
        entry['periods'].append({
            'start': period.start_date.isoformat(),
            'end': period.end_date.isoformat(),
        })
    return list(by_request.values())


def find_overlapping_requests_for_periods(user, periods, exclude_request_id=None):
    """
    Βρίσκει υπάρχουσες αιτήσεις που επικαλύπτονται με τα δοθέντα διαστήματα.

    periods: iterable of dicts με 'start_date' / 'end_date' (date objects)
    Επιστρέφει λίστα ίδιας μορφής με serialize_..., μόνο με τα επικαλυπτόμενα διαστήματα.
    """
    if not periods:
        return []

    existing = serialize_user_leave_periods_for_overlap(
        user, exclude_request_id=exclude_request_id,
    )
    conflicts = []
    for lr in existing:
        overlapping_periods = []
        for ep in lr['periods']:
            ep_start = ep['start']
            ep_end = ep['end']
            for period in periods:
                start = period['start_date']
                end = period['end_date']
                start_iso = start.isoformat() if hasattr(start, 'isoformat') else str(start)
                end_iso = end.isoformat() if hasattr(end, 'isoformat') else str(end)
                if start_iso <= ep_end and end_iso >= ep_start:
                    overlapping_periods.append(ep)
                    break
        if overlapping_periods:
            conflicts.append({
                'id': lr['id'],
                'leave_type': lr['leave_type'],
                'status': lr['status'],
                'periods': overlapping_periods,
            })
    return conflicts
