"""Context processors για leaves app."""
from leaves.role_context import get_role_nav_items


def role_switcher(request):
    """Role switcher navigation για authenticated χρήστες."""
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}
    return {
        'role_nav_items': get_role_nav_items(request.user, request),
    }
