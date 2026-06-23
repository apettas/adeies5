"""Project-level template context processors."""


def csp_nonce(request):
    """Nonce για inline scripts στο CSP."""
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}
