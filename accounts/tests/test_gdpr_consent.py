"""Tests για popup συγκατάθεσης GDPR μετά το πρώτο login."""
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.gdpr_consent import GDPR_CONSENT_TEXT, GDPR_CONSENT_VERSION, user_needs_gdpr_consent
from accounts.models import GDPRConsent
from accounts.tests.test_data import TestDataMixin


class GDPRConsentTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.employee.registration_status = 'APPROVED'
        self.employee.is_active = True
        self.employee.gdpr_consent_accepted_at = None
        self.employee.gdpr_consent_version = 0
        self.employee.save()

    def test_needs_consent_when_missing(self):
        self.assertTrue(user_needs_gdpr_consent(self.employee))

    def test_does_not_need_consent_after_accept(self):
        self.employee.gdpr_consent_accepted_at = timezone.now()
        self.employee.gdpr_consent_version = GDPR_CONSENT_VERSION
        self.employee.save(update_fields=['gdpr_consent_accepted_at', 'gdpr_consent_version'])
        self.assertFalse(user_needs_gdpr_consent(self.employee))

    def test_modal_shown_on_dashboard_before_consent(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse('leaves:employee_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'gdprConsentModal')
        self.assertContains(response, 'Συγκατάθεση Επεξεργασίας Προσωπικών Δεδομένων')

    def test_modal_hidden_after_consent(self):
        self.employee.gdpr_consent_accepted_at = timezone.now()
        self.employee.gdpr_consent_version = GDPR_CONSENT_VERSION
        self.employee.save(update_fields=['gdpr_consent_accepted_at', 'gdpr_consent_version'])
        self.client.force_login(self.employee)
        response = self.client.get(reverse('leaves:employee_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'gdprConsentModal')

    def test_accept_requires_both_checkboxes(self):
        self.client.force_login(self.employee)
        url = reverse('accounts:accept_gdpr_consent')
        response = self.client.post(url, {'consent': 'true'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(GDPRConsent.objects.filter(employee=self.employee).count(), 0)

        response = self.client.post(url, {'do_not_show_again': 'true'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(GDPRConsent.objects.filter(employee=self.employee).count(), 0)

    def test_accept_stores_consent_and_hides_modal(self):
        self.client.force_login(self.employee)
        url = reverse('accounts:accept_gdpr_consent')
        response = self.client.post(url, {
            'consent': 'true',
            'do_not_show_again': 'true',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

        self.employee.refresh_from_db()
        self.assertIsNotNone(self.employee.gdpr_consent_accepted_at)
        self.assertEqual(self.employee.gdpr_consent_version, GDPR_CONSENT_VERSION)

        consent = GDPRConsent.objects.get(employee=self.employee)
        self.assertEqual(consent.version, GDPR_CONSENT_VERSION)
        self.assertEqual(consent.consent_text, GDPR_CONSENT_TEXT)
        self.assertTrue(consent.do_not_show_again)

        page = self.client.get(reverse('leaves:employee_dashboard'))
        self.assertNotContains(page, 'gdprConsentModal')
