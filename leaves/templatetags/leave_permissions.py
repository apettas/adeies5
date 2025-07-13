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
    
    # Χρήση της μεθόδου get_approving_manager από το User model
    try:
        approving_manager = leave_request.user.get_approving_manager()
        return approving_manager and approving_manager.id == user.id
    except:
        return False