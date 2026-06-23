"""Tests για security headers middleware."""
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from pdede_leaves.middleware import SecurityHeadersMiddleware


@override_settings(ALLOWED_HOSTS=['testserver'])
class SecurityHeadersMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SecurityHeadersMiddleware(lambda request: HttpResponse('ok'))

    def test_sets_csp_with_nonce_and_security_headers(self):
        request = self.factory.get('/')
        response = self.middleware(request)

        self.assertTrue(hasattr(request, 'csp_nonce'))
        self.assertIn('Content-Security-Policy', response)
        self.assertIn(f"'nonce-{request.csp_nonce}'", response['Content-Security-Policy'])
        self.assertNotIn('unsafe-inline', response['Content-Security-Policy'].split('script-src')[1].split(';')[0])
        self.assertEqual(response['Referrer-Policy'], 'strict-origin-when-cross-origin')
        self.assertEqual(response['Cross-Origin-Resource-Policy'], 'same-origin')
        self.assertIn("object-src 'none'", response['Content-Security-Policy'])
        self.assertIn("frame-ancestors 'none'", response['Content-Security-Policy'])

    def test_does_not_override_existing_csp(self):
        def view(request):
            response = HttpResponse('ok')
            response['Content-Security-Policy'] = "default-src 'none'"
            return response

        middleware = SecurityHeadersMiddleware(view)
        response = middleware(self.factory.get('/'))
        self.assertEqual(response['Content-Security-Policy'], "default-src 'none'")
