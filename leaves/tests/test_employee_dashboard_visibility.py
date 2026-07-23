"""Tests για ορατότητα καρτών στο employee dashboard βάσει employee_type."""
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import EmployeeType
from accounts.tests.test_data import TestDataMixin


class EmployeeDashboardVisibilityTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.admin_type, _ = EmployeeType.objects.get_or_create(
            code='ADMINISTRATIVE',
            defaults={'name': 'Διοικητικοί', 'description': 'Διοικητικοί', 'is_permanent_dy': False},
        )
        self.permanent_type, _ = EmployeeType.objects.get_or_create(
            code='EDUCATIONAL',
            defaults={'name': 'Εκπαιδευτικοί', 'description': 'Εκπαιδευτικοί', 'is_permanent_dy': True},
        )
        if not self.permanent_type.is_permanent_dy:
            self.permanent_type.is_permanent_dy = True
            self.permanent_type.save(update_fields=['is_permanent_dy'])
        # Αποφυγή GDPR modal στα assertions
        self.employee.gdpr_consent_accepted_at = timezone.now()
        self.employee.gdpr_consent_version = 1
        self.employee.save(update_fields=['gdpr_consent_accepted_at', 'gdpr_consent_version'])

    def test_administrative_sees_regular_balance_only(self):
        self.employee.employee_type = self.admin_type
        self.employee.save(update_fields=['employee_type'])
        self.client.force_login(self.employee)
        response = self.client.get(reverse('leaves:employee_dashboard'))
        self.assertContains(response, 'Υπόλοιπο Κανονικών Αδειών')
        self.assertNotContains(response, 'Αναρρωτικές με Υπεύθυνη Δήλωση τρέχοντος έτους')
        self.assertNotContains(response, 'Σύνολο Αναρρωτικών τρέχοντος έτους')

    def test_permanent_dy_sees_sick_cards_only(self):
        self.employee.employee_type = self.permanent_type
        self.employee.save(update_fields=['employee_type'])
        self.client.force_login(self.employee)
        response = self.client.get(reverse('leaves:employee_dashboard'))
        self.assertNotContains(response, 'Υπόλοιπο Κανονικών Αδειών')
        self.assertContains(response, 'Αναρρωτικές με Υπεύθυνη Δήλωση τρέχοντος έτους')
        self.assertContains(response, 'Σύνολο Αναρρωτικών τρέχοντος έτους')
        self.assertContains(response, 'όριο για Υγειονομική επιτροπή')

    def test_other_type_sees_neither(self):
        other, _ = EmployeeType.objects.get_or_create(
            code='OTHER',
            defaults={'name': 'Άλλο', 'description': 'Άλλο', 'is_permanent_dy': False},
        )
        self.employee.employee_type = other
        self.employee.save(update_fields=['employee_type'])
        self.client.force_login(self.employee)
        response = self.client.get(reverse('leaves:employee_dashboard'))
        self.assertNotContains(response, 'Υπόλοιπο Κανονικών Αδειών')
        self.assertNotContains(response, 'Αναρρωτικές με Υπεύθυνη Δήλωση τρέχοντος έτους')
