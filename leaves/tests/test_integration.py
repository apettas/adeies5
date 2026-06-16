"""
Integration tests for complete leave approval workflows
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch

from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveRequest, LeaveType
from leaves.tests.helpers import create_submitted_leave_request, complete_leave_as_handler, advance_leave_to_in_review

User = get_user_model()


class CompleteLeaveApprovalWorkflowTests(TestDataMixin, TestCase):
    """Integration tests για complete leave approval workflows"""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25,
        )
        for user in [self.employee, self.dept_manager, self.kizilou, self.delegkos]:
            user.current_regular_leave_balance = 25
            user.save()

    def test_complete_employee_approval_workflow(self):
        leave_request = create_submitted_leave_request(
            self.employee,
            self.leave_type,
            'Integration test leave request',
            '2025-01-15',
            '2025-01-20',
        )

        self.client.force_login(self.dept_manager)
        response = self.client.get(reverse('leaves:manager_dashboard'))
        self.assertContains(response, 'Integration test leave request')

        response = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': leave_request.pk})
        )
        self.assertEqual(response.status_code, 302)

        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'PENDING_PROTOCOL')
        self.assertEqual(leave_request.manager_approved_by, self.dept_manager)

        self.client.force_login(self.leave_handler)
        response = self.client.get(reverse('leaves:handler_dashboard'))
        self.assertContains(response, 'Υπάλληλος Τεστ')

        advance_leave_to_in_review(self.client, leave_request)
        response = complete_leave_as_handler(self.client, leave_request, balance_after=19)
        self.assertEqual(response.status_code, 302)

        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'COMPLETED')
        self.assertEqual(leave_request.processed_by, self.leave_handler)

    def test_complete_department_manager_approval_workflow(self):
        leave_request = create_submitted_leave_request(
            self.dept_manager,
            self.leave_type,
            'Department manager leave request',
            '2025-02-15',
            '2025-02-20',
        )

        self.client.force_login(self.kizilou)
        response = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': leave_request.pk})
        )
        self.assertEqual(response.status_code, 302)

        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'PENDING_PROTOCOL')
        self.assertEqual(leave_request.manager_approved_by, self.kizilou)

        self.client.force_login(self.leave_handler)
        advance_leave_to_in_review(self.client, leave_request)
        response = complete_leave_as_handler(self.client, leave_request, balance_after=19)
        self.assertEqual(response.status_code, 302)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'COMPLETED')

    def test_complete_kizilou_approval_workflow(self):
        leave_request = create_submitted_leave_request(
            self.kizilou,
            self.leave_type,
            'kizilou leave request',
            '2025-03-15',
            '2025-03-20',
        )

        self.client.force_login(self.delegkos)
        response = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': leave_request.pk})
        )
        self.assertEqual(response.status_code, 302)

        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'PENDING_PROTOCOL')

        self.client.force_login(self.leave_handler)
        advance_leave_to_in_review(self.client, leave_request)
        response = complete_leave_as_handler(self.client, leave_request, balance_after=19)
        self.assertEqual(response.status_code, 302)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'COMPLETED')

    def test_complete_delegkos_approval_workflow(self):
        leave_request = create_submitted_leave_request(
            self.delegkos,
            self.leave_type,
            'delegkos leave request',
            '2025-04-15',
            '2025-04-20',
        )
        leave_request.status = 'PENDING_PROTOCOL'
        leave_request.manager_approved_by = self.delegkos
        leave_request.save()

        self.client.force_login(self.leave_handler)
        response = self.client.get(reverse('leaves:handler_dashboard'))
        self.assertContains(response, 'Δελέγκος Τεστ')

        advance_leave_to_in_review(self.client, leave_request)
        response = complete_leave_as_handler(self.client, leave_request, balance_after=19)
        self.assertEqual(response.status_code, 302)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'COMPLETED')


class LeaveApprovalRejectionWorkflowTests(TestDataMixin, TestCase):
    """Integration tests για rejection workflows"""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25,
        )

    def test_employee_request_rejection_workflow(self):
        leave_request = create_submitted_leave_request(
            self.employee,
            self.leave_type,
            'Rejection test request',
            '2025-01-15',
            '2025-01-20',
        )

        self.client.force_login(self.dept_manager)
        response = self.client.post(
            reverse('leaves:reject_leave_request', kwargs={'pk': leave_request.pk}),
            {'reason': 'Test rejection reason'},
        )
        self.assertEqual(response.status_code, 302)

        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'SUPERVISOR_REJECTED')

        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': leave_request.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="approveModal')

    def test_request_cancellation_workflow(self):
        leave_request = create_submitted_leave_request(
            self.employee,
            self.leave_type,
            'Cancellation test request',
            '2025-02-15',
            '2025-02-20',
        )

        self.client.force_login(self.employee)
        response = self.client.post(
            reverse('leaves:withdraw_leave_request', kwargs={'pk': leave_request.pk})
        )
        self.assertEqual(response.status_code, 302)

        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'CANCELLED_BY_APPLICANT')

        response = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': leave_request.pk})
        )
        self.assertEqual(response.status_code, 403)
        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'CANCELLED_BY_APPLICANT')


class MultipleRequestsWorkflowTests(TestDataMixin, TestCase):
    """Integration tests για multiple requests"""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25,
        )
        self.requests = [
            create_submitted_leave_request(
                self.employee, self.leave_type, f'Batch request {i}',
                f'2025-0{i+1}-15', f'2025-0{i+1}-20',
            )
            for i in range(1, 4)
        ]

    def test_batch_approval_workflow(self):
        self.client.force_login(self.dept_manager)
        for request in self.requests:
            response = self.client.post(
                reverse('leaves:approve_leave_request', kwargs={'pk': request.pk})
            )
            self.assertEqual(response.status_code, 302)
            request.refresh_from_db()
            self.assertEqual(request.status, 'PENDING_PROTOCOL')

    def test_mixed_approval_rejection_workflow(self):
        self.client.force_login(self.dept_manager)
        self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': self.requests[0].pk})
        )
        self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': self.requests[1].pk})
        )
        self.client.post(
            reverse('leaves:reject_leave_request', kwargs={'pk': self.requests[2].pk}),
            {'reason': 'Test rejection'},
        )

        self.requests[0].refresh_from_db()
        self.requests[1].refresh_from_db()
        self.requests[2].refresh_from_db()
        self.assertEqual(self.requests[0].status, 'PENDING_PROTOCOL')
        self.assertEqual(self.requests[1].status, 'PENDING_PROTOCOL')
        self.assertEqual(self.requests[2].status, 'SUPERVISOR_REJECTED')

    def test_dashboard_filtering_with_multiple_requests(self):
        self.requests[0].approve_by_manager(self.dept_manager)
        self.requests[1].approve_by_manager(self.dept_manager)
        self.requests[2].reject_by_manager(self.dept_manager, 'Rejected')

        self.client.force_login(self.employee)
        response = self.client.get(
            reverse('leaves:employee_dashboard'), {'status': 'PENDING_PROTOCOL'}
        )
        self.assertContains(response, '15/02/2025')
        self.assertContains(response, '15/03/2025')
        self.assertNotContains(response, '15/04/2025')


class LeaveBalanceIntegrationTests(TestDataMixin, TestCase):
    """Integration tests για leave balance"""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25,
            affects_regular_leave_balance=True,
        )
        self.employee.current_regular_leave_balance = 25
        self.employee.save()

    def test_leave_balance_validation_workflow(self):
        self.employee.current_regular_leave_balance = 2
        self.employee.save()

        leave_request = LeaveRequest(
            user=self.employee,
            leave_type=self.leave_type,
            description='Over balance request',
            status='DRAFT',
        )
        leave_request.save()
        from leaves.models import LeavePeriod
        LeavePeriod.objects.create(
            leave_request=leave_request,
            start_date='2025-05-01',
            end_date='2025-05-10',
        )

        with self.assertRaises(ValueError):
            leave_request.submit()

    def test_leave_balance_update_after_approval(self):
        leave_request = create_submitted_leave_request(
            self.employee,
            self.leave_type,
            'Balance update request',
            '2025-06-01',
            '2025-06-06',
        )
        leave_request.approve_by_manager(self.dept_manager)

        self.client.force_login(self.leave_handler)
        advance_leave_to_in_review(self.client, leave_request)
        complete_leave_as_handler(self.client, leave_request, balance_after=19)

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.current_regular_leave_balance, 19)
        self.assertEqual(self.employee.leave_balance, 19)


class NotificationIntegrationTests(TestDataMixin, TestCase):
    """Integration tests για notifications"""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25,
        )

    @patch('leaves.views.create_notification')
    def test_email_notification_workflow(self, mock_create_notification):
        leave_request = create_submitted_leave_request(
            self.employee,
            self.leave_type,
            'Notification test request',
            '2025-01-15',
            '2025-01-20',
        )

        self.client.force_login(self.dept_manager)
        self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': leave_request.pk})
        )
        self.assertTrue(mock_create_notification.called)

    def test_dashboard_notification_workflow(self):
        create_submitted_leave_request(
            self.employee,
            self.leave_type,
            'Dashboard notification request',
            '2025-01-15',
            '2025-01-20',
        )

        self.client.force_login(self.dept_manager)
        response = self.client.get(reverse('leaves:manager_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Υπάλληλος Τεστ')


class ErrorHandlingIntegrationTests(TestDataMixin, TestCase):
    """Integration tests για error handling"""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25,
        )

    def test_concurrent_approval_handling(self):
        leave_request = create_submitted_leave_request(
            self.employee,
            self.leave_type,
            'Concurrent approval request',
            '2025-01-15',
            '2025-01-20',
        )

        self.client.force_login(self.dept_manager)
        response1 = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': leave_request.pk})
        )
        self.assertEqual(response1.status_code, 302)

        response2 = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': leave_request.pk})
        )
        self.assertIn(response2.status_code, [302, 403])

    def test_invalid_request_handling(self):
        self.client.force_login(self.dept_manager)
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': 99999})
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': 99999})
        )
        self.assertEqual(response.status_code, 404)

    def test_permission_edge_cases(self):
        leave_request = create_submitted_leave_request(
            self.employee,
            self.leave_type,
            'Permission edge case request',
            '2025-01-15',
            '2025-01-20',
        )

        self.client.force_login(self.kizilou)
        response = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': leave_request.pk})
        )
        self.assertEqual(response.status_code, 403)

        leave_request.refresh_from_db()
        self.assertEqual(leave_request.status, 'SUBMITTED')
