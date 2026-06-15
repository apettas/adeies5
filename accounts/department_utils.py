"""Βοηθητικά για αναγνώριση τύπων τμημάτων (ΣΔΕΥ/ΚΕΔΑΣΥ)."""

# Legacy installations χρησιμοποιούν SDEI αντί SDEY για τα ίδια τμήματα.
SDEY_DEPARTMENT_TYPE_CODES = ('SDEY', 'SDEI')
KEDASY_KEPEA_DEPARTMENT_TYPE_CODES = ('KEDASY', 'KEPEA')


def is_sdey_department(department):
    """True αν το τμήμα είναι ΣΔΕΥ (SDEY ή legacy SDEI)."""
    if not department or not department.department_type:
        return False
    return department.department_type.code in SDEY_DEPARTMENT_TYPE_CODES


def is_kedasy_or_kepea_department(department):
    if not department or not department.department_type:
        return False
    return department.department_type.code in KEDASY_KEPEA_DEPARTMENT_TYPE_CODES


def is_sdey_under_kedasy(department):
    """ΣΔΕΥ με γονικό ΚΕΔΑΣΥ — ειδική ροή πρωτοκόλλου/έγκρισης."""
    if not is_sdey_department(department):
        return False
    parent = department.parent_department
    return bool(
        parent
        and parent.department_type
        and parent.department_type.code == 'KEDASY'
    )
