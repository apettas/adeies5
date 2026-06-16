"""
Role switcher και default dashboard routing για multi-role χρήστες.
"""
from django.db.models import Q
from django.urls import reverse

from accounts.department_utils import SDEY_DEPARTMENT_TYPE_CODES
from leaves.models import LeaveRequest

ROLE_NAV_CONFIG = {
    'employee': {
        'label': 'Οι αιτήσεις μου',
        'icon': 'bi-person-circle',
        'url_name': 'leaves:employee_dashboard',
    },
    'manager': {
        'label': 'Προϊστάμενος',
        'icon': 'bi-clipboard-check',
        'url_name': 'leaves:manager_dashboard',
    },
    'handler': {
        'label': 'Χειριστής Αδειών',
        'icon': 'bi-gear',
        'url_name': 'leaves:handler_dashboard',
    },
    'secretary': {
        'label': 'Γραμματέας',
        'icon': 'bi-archive',
        'url_name': 'leaves:secretary_dashboard',
    },
    'admin': {
        'label': 'Διαχείριση',
        'icon': 'bi-people-fill',
        'url_name': 'accounts:manage_roles',
    },
}

URL_NAME_TO_ROLE = {
    'employee_dashboard': 'employee',
    'manager_dashboard': 'manager',
    'handler_dashboard': 'handler',
    'secretary_dashboard': 'secretary',
    'manage_roles': 'admin',
}

ROLE_PRIORITY = ['manager', 'handler', 'secretary', 'employee', 'admin']


def _secretary_department_filter(user):
    """Φίλτρο τμήματος για γραμματέα (ΚΕΔΑΣΥ + ΣΔΕΥ)."""
    if not user.department_id:
        return None
    department_filter = Q(user__department=user.department)
    if (user.department.department_type and
            user.department.department_type.code == 'KEDASY'):
        sdei_filter = Q(
            user__department__department_type__code__in=SDEY_DEPARTMENT_TYPE_CODES,
            user__department__parent_department=user.department,
        )
        department_filter = department_filter | sdei_filter
    return department_filter


def get_role_pending_counts(user):
    """Εκκρεμότητες ανά ρόλο για badges στο role switcher."""
    counts = {
        'employee': 0,
        'manager': 0,
        'handler': 0,
        'secretary': 0,
        'admin': 0,
    }
    if not user.is_authenticated:
        return counts

    counts['employee'] = LeaveRequest.objects.filter(
        user=user,
        status__in=['SUBMITTED', 'PENDING_PROTOCOL', 'WAITING_FOR_DOCUMENTS'],
    ).count()

    if user.is_department_manager:
        subordinates = user.get_subordinates()
        counts['manager'] = LeaveRequest.objects.filter(
            user__in=subordinates,
            status='SUBMITTED',
        ).count()

    if user.is_leave_handler:
        counts['handler'] = LeaveRequest.objects.filter(
            status='PENDING_PROTOCOL',
        ).count()

    if user.is_secretary:
        dept_filter = _secretary_department_filter(user)
        if dept_filter is not None:
            counts['secretary'] = LeaveRequest.objects.filter(
                status='PENDING_KEDASY_PROTOCOL',
            ).filter(dept_filter).count()

    return counts


def user_has_dashboard_role(user, role_key):
    """Έλεγχος αν ο χρήστης έχει πρόσβαση στο dashboard ρόλου."""
    checks = {
        'employee': lambda u: u.has_leave_request_permission() or u.is_employee or True,
        'manager': lambda u: u.is_department_manager,
        'handler': lambda u: u.is_leave_handler,
        'secretary': lambda u: u.is_secretary,
        'admin': lambda u: u.is_administrator,
    }
    return checks.get(role_key, lambda u: False)(user)


def get_active_role_key(request):
    """Εντοπίζει τον ενεργό ρόλο από το URL."""
    if not request or not getattr(request, 'resolver_match', None):
        return None
    url_name = request.resolver_match.url_name
    return URL_NAME_TO_ROLE.get(url_name)


def get_role_nav_items(user, request=None):
    """Λίστα κουμπιών role switcher με badges."""
    if not user.is_authenticated:
        return []

    counts = get_role_pending_counts(user)
    active_role = get_active_role_key(request)
    items = []

    role_order = ['employee', 'manager', 'handler', 'secretary', 'admin']
    for role_key in role_order:
        if not user_has_dashboard_role(user, role_key):
            continue
        config = ROLE_NAV_CONFIG[role_key]
        items.append({
            'key': role_key,
            'label': config['label'],
            'icon': config['icon'],
            'url': reverse(config['url_name']),
            'badge': counts.get(role_key, 0),
            'is_active': role_key == active_role,
        })
    return items


def resolve_default_dashboard_name(user, session=None):
    """
    Επιλογή default dashboard μετά login:
    1) ρόλος με εκκρεμότητες, 2) session, 3) handler > manager > secretary > employee.
    """
    session = session or {}
    counts = get_role_pending_counts(user)

    for role_key in ROLE_PRIORITY:
        if counts.get(role_key, 0) > 0 and user_has_dashboard_role(user, role_key):
            return ROLE_NAV_CONFIG[role_key]['url_name']

    last_role = session.get('active_dashboard_role')
    if last_role and user_has_dashboard_role(user, last_role):
        return ROLE_NAV_CONFIG[last_role]['url_name']

    for role_key in ROLE_PRIORITY:
        if user_has_dashboard_role(user, role_key):
            return ROLE_NAV_CONFIG[role_key]['url_name']

    return ROLE_NAV_CONFIG['employee']['url_name']
