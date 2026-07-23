"""Tests για ενότητα Αναφορών."""
from django.test import TestCase
from django.urls import reverse

from accounts.tests.test_data import TestDataMixin


class ReportsViewsTests(TestDataMixin, TestCase):
    def test_handler_sees_reports_index(self):
        self.client.force_login(self.leave_handler)
        response = self.client.get(reverse('leaves:reports_index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Προϊστάμενοι ανά Τμήμα')
        self.assertContains(response, 'Παρουσιολόγιο')

    def test_department_managers_report(self):
        self.client.force_login(self.leave_handler)
        response = self.client.get(reverse('leaves:report_department_managers'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.child_department.name)
        self.assertContains(response, self.dept_manager.last_name)

    def test_employee_forbidden(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse('leaves:reports_index')).status_code, 403)
        self.assertEqual(
            self.client.get(reverse('leaves:report_department_managers')).status_code,
            403,
        )
