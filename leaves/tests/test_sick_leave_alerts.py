"""Tests για alert Υγειονομικής Επιτροπής (>8 αναρρωτικές ημέρες)."""
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveType, YCCommitteeAcknowledgment
from leaves.tests.helpers import create_submitted_leave_request, create_draft_leave_request
from notifications.models import Notification
from leaves.utils.sick_leave_alerts import (
    calculate_yearly_sick_total,
    can_acknowledge_sick_alert,
    get_sick_alert_users,
    user_has_acknowledged_own_sick_alert,
)


class SickLeaveAlertTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.sick_total_type = LeaveType.objects.create(
            name='Αναρρωτική σύνολο',
            code='TEST_SICK_TOTAL',
            requires_approval=True,
            is_sick_leave_total=True,
            affects_regular_leave_balance=False,
        )
        self.client = Client()

    def _create_exceeding_sick_leave(self, user=None, days=5, start='2026-01-06', end='2026-01-10'):
        user = user or self.employee
        req = create_submitted_leave_request(
            user, self.sick_total_type, 'sick', start, end,
        )
        req.submitted_at = timezone.now()
        req.save()
        return req

    def test_calculate_yearly_sick_total_includes_submitted_requests(self):
        self._create_exceeding_sick_leave(days=5, start='2026-02-03', end='2026-02-12')
        total = calculate_yearly_sick_total(self.employee)
        self.assertEqual(total, 10)
        self.assertGreater(total, 8)

    def test_handler_sees_alert_until_acknowledged(self):
        self._create_exceeding_sick_leave(start='2026-03-03', end='2026-03-12')
        alerts = get_sick_alert_users(self.leave_handler)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].pk, self.employee.pk)
        self.assertEqual(alerts[0].sick_alert_days, 10)

        YCCommitteeAcknowledgment.objects.create(
            handler=self.leave_handler,
            employee=self.employee,
        )
        self.assertEqual(get_sick_alert_users(self.leave_handler), [])

    def test_manager_sees_subordinate_alert_and_can_acknowledge(self):
        self._create_exceeding_sick_leave(start='2026-04-07', end='2026-04-16')
        alerts = get_sick_alert_users(
            self.dept_manager,
            scope_user_ids=self.dept_manager.get_subordinates().values_list('id', flat=True),
        )
        self.assertEqual(len(alerts), 1)
        self.assertTrue(can_acknowledge_sick_alert(self.dept_manager, self.employee))

        self.client.force_login(self.dept_manager)
        response = self.client.get(
            reverse('leaves:acknowledge_yc_alert', kwargs={'user_id': self.employee.pk})
        )
        self.assertRedirects(response, reverse('leaves:manager_dashboard'))
        self.assertEqual(get_sick_alert_users(self.dept_manager, scope_user_ids=[self.employee.pk]), [])

    def test_employee_dashboard_hides_alert_after_self_acknowledge(self):
        self._create_exceeding_sick_leave(start='2026-05-05', end='2026-05-14')
        self.assertFalse(user_has_acknowledged_own_sick_alert(self.employee))

        self.client.force_login(self.employee)
        response = self.client.get(reverse('leaves:employee_dashboard'))
        self.assertContains(response, 'Έλαβα Γνώση')
        self.assertContains(response, 'υπέρβαση ορίου 8 ημερών')

        self.client.get(reverse('leaves:acknowledge_yc_alert', kwargs={'user_id': self.employee.pk}))
        self.assertTrue(user_has_acknowledged_own_sick_alert(self.employee))

        response = self.client.get(reverse('leaves:employee_dashboard'))
        self.assertNotContains(response, 'Έλαβα Γνώση')

    def test_submit_resets_acknowledgments_and_notifies_all_roles(self):
        """Νέα υποβολή >8 ημερών επαναφέρει το alert και στέλνει ειδοποιήσεις."""
        prior = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'prior', '2026-02-03', '2026-02-12',
        )
        prior.status = 'COMPLETED'
        prior.save()

        YCCommitteeAcknowledgment.objects.create(
            handler=self.leave_handler, employee=self.employee,
        )
        YCCommitteeAcknowledgment.objects.create(
            handler=self.dept_manager, employee=self.employee,
        )
        YCCommitteeAcknowledgment.objects.create(
            handler=self.employee, employee=self.employee,
        )

        new_req = create_draft_leave_request(
            self.employee, self.sick_total_type, 'new sick', '2026-06-21', '2026-06-23',
        )
        new_req.submit()

        self.assertFalse(
            YCCommitteeAcknowledgment.objects.filter(employee=self.employee).exists()
        )
        alerts = get_sick_alert_users(self.leave_handler)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].sick_alert_days, 13)

        self.assertTrue(
            Notification.objects.filter(
                user=self.leave_handler,
                title__contains='Υπέρβαση Αναρρωτικών',
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.dept_manager,
                title__contains='Υπέρβαση Αναρρωτικών',
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.employee,
                title__contains='Υπέρβαση Αναρρωτικών',
            ).exists()
        )
