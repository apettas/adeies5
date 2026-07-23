"""Project-level template context processors."""


def csp_nonce(request):
    """Nonce για inline scripts στο CSP."""
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}


def gdpr_consent(request):
    """Σημαία/κείμενο για το popup συγκατάθεσης GDPR μετά το πρώτο login."""
    from accounts.gdpr_consent import (
        GDPR_CONSENT_TEXT,
        GDPR_CONSENT_TITLE,
        GDPR_CONSENT_VERSION,
        user_needs_gdpr_consent,
    )

    # Μην εμποδίζεις την ανάγνωση της Πολιτικής Απορρήτου
    path = getattr(request, 'path', '') or ''
    if path.rstrip('/').endswith('/privacy-policy'):
        needs = False
    else:
        user = getattr(request, 'user', None)
        needs = user_needs_gdpr_consent(user)
    return {
        'needs_gdpr_consent': needs,
        'gdpr_consent_title': GDPR_CONSENT_TITLE,
        'gdpr_consent_text': GDPR_CONSENT_TEXT,
        'gdpr_consent_version': GDPR_CONSENT_VERSION,
    }
