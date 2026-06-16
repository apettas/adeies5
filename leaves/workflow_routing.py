"""
Κανόνες δρομολόγησης workflow βάσει workflow_variant του τύπου άδειας και τμήματος.
"""
from accounts.department_utils import (
    is_kedasy_or_kepea_department,
    is_sdey_department,
    is_sdey_under_kedasy,
)

WORKFLOW_STANDARD = 'STANDARD'
WORKFLOW_KEDASY = 'KEDASY'
WORKFLOW_SDEY = 'SDEY'


def get_leave_workflow_variant(leave_type):
    """Επιστρέφει τον κανονικοποιημένο κωδικό variant."""
    return (getattr(leave_type, 'workflow_variant', None) or WORKFLOW_STANDARD).upper()


def leave_request_requires_kedasy_protocol(leave_request):
    """
    Αν η αίτηση πρέπει να περάσει από πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ πριν την έγκριση.

    - KEDASY variant: ΚΕΔΑΣΥ, ΚΕΠΕΑ ή ΣΔΕΥ υπό ΚΕΔΑΣΥ
    - SDEY variant: μόνο ΣΔΕΥ υπό ΚΕΔΑΣΥ
    - STANDARD variant: ίδια λογική με τύπο τμήματος (backward compatible)
    """
    department = leave_request.user.department
    variant = get_leave_workflow_variant(leave_request.leave_type)

    if variant == WORKFLOW_KEDASY:
        return bool(
            is_kedasy_or_kepea_department(department)
            or is_sdey_under_kedasy(department)
        )
    if variant == WORKFLOW_SDEY:
        return is_sdey_under_kedasy(department)
    if variant == WORKFLOW_STANDARD:
        if not department or not department.department_type:
            return False
        if is_kedasy_or_kepea_department(department):
            return True
        return is_sdey_under_kedasy(department)
    return False


def kedasy_protocol_target_department(leave_request):
    """Τμήμα που χειρίζεται το πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ."""
    department = leave_request.user.department
    if not department:
        return None
    if is_sdey_department(department) and department.parent_department:
        return department.parent_department
    return department
