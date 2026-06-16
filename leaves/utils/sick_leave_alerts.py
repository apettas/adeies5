"""
Υπολογισμός και εμφάνιση alert Υγειονομικής Επιτροπής (>8 αναρρωτικές ημέρες/έτος).
"""
from django.utils import timezone

from leaves.models import LeaveRequest, YCCommitteeAcknowledgment

SICK_LEAVE_THRESHOLD = 8

EXCLUDED_SICK_STATUSES = [
    'DRAFT',
    'SUPERVISOR_REJECTED',
    'REJECTED_BY_LEAVES_DEPT',
    'CANCELLED_BY_APPLICANT',
]


def calculate_yearly_sick_total(user, year=None):
    """Σύνολο αναρρωτικών ημερών τρέχοντος έτους (ενεργές + ολοκληρωμένες αιτήσεις)."""
    year = year or timezone.now().year
    sick_lrs = LeaveRequest.objects.filter(
        user=user,
        leave_type__is_sick_leave_total=True,
        submitted_at__year=year,
    ).exclude(
        status__in=EXCLUDED_SICK_STATUSES,
    ).prefetch_related('periods')
    return sum(lr.total_days for lr in sick_lrs)


def get_yearly_sick_totals_by_user(year=None, user_ids=None):
    """Λεξικό user_id -> σύνολο αναρρωτικών ημερών για το έτος."""
    year = year or timezone.now().year
    sick_lrs = LeaveRequest.objects.filter(
        leave_type__is_sick_leave_total=True,
        submitted_at__year=year,
    ).exclude(
        status__in=EXCLUDED_SICK_STATUSES,
    ).select_related('user').prefetch_related('periods')
    if user_ids is not None:
        sick_lrs = sick_lrs.filter(user_id__in=user_ids)

    totals = {}
    for lr in sick_lrs:
        totals[lr.user_id] = totals.get(lr.user_id, 0) + lr.total_days
    return totals


def get_acknowledged_employee_ids(viewer):
    """Υπάλληλοι για τους οποίους ο viewer έχει δηλώσει «Έλαβα γνώση»."""
    return set(
        YCCommitteeAcknowledgment.objects.filter(
            handler=viewer,
        ).values_list('employee_id', flat=True)
    )


def _attach_alert_days(user, days):
    """Προσάρτηση υπολογισμένων ημερών στο αντικείμενο User για templates."""
    user.sick_alert_days = days
    return user


def get_sick_alert_users(viewer, *, scope_user_ids=None, year=None):
    """
    Υπάλληλοι με >8 αναρρωτικές ημέρες που δεν έχουν αναγνωριστεί από τον viewer.

    scope_user_ids: περιορισμός σε συγκεκριμένους υπαλλήλους (π.χ. υφιστάμενοι).
    """
    year = year or timezone.now().year
    totals = get_yearly_sick_totals_by_user(year=year, user_ids=scope_user_ids)
    acknowledged = get_acknowledged_employee_ids(viewer)

    alert_ids = [
        uid for uid, total in totals.items()
        if total > SICK_LEAVE_THRESHOLD and uid not in acknowledged
    ]
    if not alert_ids:
        return []

    from accounts.models import User
    users = User.objects.filter(
        id__in=alert_ids,
        is_active=True,
    ).select_related('department').prefetch_related('roles').order_by('last_name', 'first_name')

    return [_attach_alert_days(user, totals[user.id]) for user in users]


def user_exceeds_sick_threshold(user, year=None):
    """Έλεγχος αν ο υπάλληλος ξεπερνά το όριο αναρρωτικών."""
    return calculate_yearly_sick_total(user, year=year) > SICK_LEAVE_THRESHOLD


def user_has_acknowledged_own_sick_alert(user, year=None):
    """Έχει ο ίδιος ο υπάλληλος δηλώσει γνώση για την υπέρβαση."""
    if not user_exceeds_sick_threshold(user, year=year):
        return True
    return YCCommitteeAcknowledgment.objects.filter(
        handler=user,
        employee=user,
    ).exists()


def can_acknowledge_sick_alert(viewer, employee):
    """Έλεγχος δικαιώματος δήλωσης «Έλαβα γνώση»."""
    if not viewer.is_authenticated or viewer.pk == employee.pk:
        return viewer.is_authenticated and viewer.pk == employee.pk
    if viewer.is_leave_handler:
        return True
    if viewer.is_department_manager:
        return employee.id in viewer.get_subordinates().values_list('id', flat=True)
    return False


def handle_sick_threshold_on_submit(leave_request):
    """
    Μετά την υποβολή αναρρωτικής: ειδοποιήσεις + επανεμφάνιση dashboard alert.

    Επαναφέρει τις γνώσεις «Έλαβα γνώση» ώστε χειριστής, προϊστάμενος και
    υπάλληλος να βλέπουν ξανά το alert όταν μια νέα αίτηση ξεπερνά το όριο.
    """
    if not leave_request.leave_type.is_sick_leave_total:
        return False
    if not user_exceeds_sick_threshold(leave_request.user):
        return False

    YCCommitteeAcknowledgment.objects.filter(employee=leave_request.user).delete()
    leave_request.notify_sick_leave_threshold_exceeded()
    return True
