"""Tests για alert αποτυχίας email πρωτοκόλλου."""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.tests.test_data import TestDataMixin
from leaves.models import LeavePeriod, LeaveRequest, LeaveType
from leaves.utils.protocol_email_alerts import (
    clear_protocol_email_failure,
    get_pending_protocol_email_failure_alerts,
    mark_protocol_email_failed,
)


class ProtocolEmailFailureAlertTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.leave_type = LeaveType.objects.create(
            name='Κανονική',
            code='REG',
            requires_approval=False,
            is_simple=False,
            is_active=True,
        )
        self.leave_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            description='Test',
            status='PENDING_PROTOCOL',
            submitted_at=timezone.now(),
        )
        LeavePeriod.objects.create(
            leave_request=self.leave_request,
            start_date=timezone.localdate(),
            end_date=timezone.localdate(),
        )

    def test_mark_and_acknowledge(self):
        mark_protocol_email_failed(self.leave_request)
        self.leave_request.refresh_from_db()
        self.assertIsNotNone(self.leave_request.protocol_email_failed_at)
        alerts = list(get_pending_protocol_email_failure_alerts(self.leave_handler))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].pk, self.leave_request.pk)

        self.client.force_login(self.leave_handler)
        response = self.client.get(
            reverse(
                'leaves:acknowledge_protocol_email_failure',
                kwargs={'pk': self.leave_request.pk},
            )
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(get_pending_protocol_email_failure_alerts(self.leave_handler)),
            [],
        )

    def test_clear_on_success(self):
        mark_protocol_email_failed(self.leave_request)
        clear_protocol_email_failure(self.leave_request)
        self.leave_request.refresh_from_db()
        self.assertIsNone(self.leave_request.protocol_email_failed_at)
        self.assertEqual(
            list(get_pending_protocol_email_failure_alerts(self.leave_handler)),
            [],
        )

    def test_handler_dashboard_shows_alert(self):
        mark_protocol_email_failed(self.leave_request)
        self.client.force_login(self.leave_handler)
        response = self.client.get(reverse('leaves:handler_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Αποτυχία Email Πρωτοκόλλου')
        self.assertContains(response, self.employee.get_full_name())
        self.assertContains(response, 'Έλαβα Γνώση')
