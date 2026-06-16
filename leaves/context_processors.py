"""Context processors για leaves app."""
from django.conf import settings

from leaves.role_context import get_role_nav_items


def role_switcher(request):
    """Role switcher navigation για authenticated χρήστες."""
    ctx = {
        'theme_static_version': getattr(settings, 'THEME_STATIC_VERSION', '1'),
    }
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return ctx
    ctx['role_nav_items'] = get_role_nav_items(request.user, request)
    return ctx
