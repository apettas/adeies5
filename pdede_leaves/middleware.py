"""Security headers middleware για Observatory / production hardening."""
import secrets

from django.utils.deprecation import MiddlewareMixin


class SecurityHeadersMiddleware(MiddlewareMixin):
    """CSP με nonce, Referrer-Policy και CORP για dynamic responses."""

    def process_request(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)

    def process_response(self, request, response):
        nonce = getattr(request, 'csp_nonce', None)
        if not nonce:
            return response

        # Μην αντικαθιστούμε CSP σε απαντήσεις που το ορίζουν ρητά (π.χ. admin)
        if 'Content-Security-Policy' not in response:
            response['Content-Security-Policy'] = (
                "default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}' "
                "https://cdn.jsdelivr.net https://code.jquery.com https://unpkg.com; "
                "style-src 'self' https://cdn.jsdelivr.net https://code.jquery.com 'unsafe-inline'; "
                "font-src 'self' https://cdn.jsdelivr.net data:; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            )

        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Cross-Origin-Resource-Policy'] = 'same-origin'
        return response
