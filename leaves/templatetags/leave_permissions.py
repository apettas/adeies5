from django import template

register = template.Library()

@register.simple_tag
def can_manager_approve(user, leave_request):
    """
    Ελέγχει αν ο manager μπορεί να εγκρίνει την αίτηση
    """
    if leave_request.status != 'SUBMITTED':
        return False
    
    if not user.is_department_manager:
        return False
    
    # Έλεγχος αν είναι από το ίδιο τμήμα
    if (leave_request.user.department and user.department and
        leave_request.user.department.id == user.department.id):
        return True
    
    # Έλεγχος ΚΕΔΑΣΥ-ΣΔΕΥ σχέσης
    if (user.department and user.department.department_type and
        user.department.department_type.code == 'KEDASY' and
        leave_request.user.department and leave_request.user.department.department_type and
        leave_request.user.department.department_type.code == 'SDEY' and
        leave_request.user.department.parent_department and
        leave_request.user.department.parent_department.id == user.department.id):
        return True
    
    return False