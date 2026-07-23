"""
Εκτεταμένα tests ροών αιτήσεων άδειας — όλοι οι κύριοι συνδυασμοί τύπων/ρόλων.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Department
from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveRequest, LeaveType, RegularLeaveBalanceEntry, YearlySickLeaveTotal
from leaves.tests.helpers import (
    add_kedasy_protocol,
    advance_leave_to_in_review,
    approve_leave_as_manager,
    complete_leave_as_handler,
    create_draft_leave_request,
    create_submitted_leave_request,
    reject_leave_as_handler,
    send_pdede_protocol,
    submit_leave_request,
)
from leaves.tests.workflow_mixins import KedasyWorkflowMixin
from leaves.utils.balance_ledger import get_last_balance

User = get_user_model()

START = '2025-03-03'
END = '2025-03-07'  # 5 ημέρες


class WorkflowLeaveTypesMixin:
    """Κοινοί τύποι αδειών για workflow tests."""

    def _create_leave_types(self):
        self.regular_type = LeaveType.objects.create(
            name='Κανονική Άδεια',
            code='WF_ANNUAL',
            requires_approval=True,
            affects_regular_leave_balance=True,
            max_days=25,
        )
        self.no_approval_type = LeaveType.objects.create(
            name='Άδεια χωρίς έγκριση',
            code='WF_NO_APPROVAL',
            requires_approval=False,
            affects_regular_leave_balance=False,
        )
        self.simple_type = LeaveType.objects.create(
            name='Απλή Άδεια',
            code='WF_SIMPLE',
            requires_approval=True,
            is_simple=True,
            affects_regular_leave_balance=False,
        )
        self.sick_yd_type = LeaveType.objects.create(
            name='Αναρρωτική με ΥΔ',
            code='WF_SICK_YD',
            requires_approval=True,
            is_sick_leave_yd=True,
            affects_regular_leave_balance=False,
        )
        self.sick_total_type = LeaveType.objects.create(
            name='Αναρρωτική σύνολο',
            code='WF_SICK_TOTAL',
            requires_approval=True,
            is_sick_leave_total=True,
            affects_regular_leave_balance=False,
        )
        self.revocation_type = LeaveType.objects.create(
            name='Ανάκληση Άδειας',
            code='WF_REVOCATION',
            requires_approval=True,
            is_revocation=True,
            affects_regular_leave_balance=False,
        )

    def _set_balances(self, *users, balance=25):
        for user in users:
            user.current_regular_leave_balance = balance
            user.save(update_fields=['current_regular_leave_balance'])


class SubmitRoutingTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Έλεγχος αρχικής κατεύθυνσης μετά την υποβολή."""

    def setUp(self):
        super().setUp()
        self._create_leave_types()
        self._set_balances(self.employee)

    def test_standard_with_approval_goes_to_submitted(self):
        req = create_draft_leave_request(
            self.employee, self.regular_type, 'routing', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'SUBMITTED')

    def test_standard_without_approval_skips_manager(self):
        req = create_draft_leave_request(
            self.employee, self.no_approval_type, 'no mgr', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'PENDING_PROTOCOL')

    def test_insufficient_balance_blocks_submit(self):
        self.employee.current_regular_leave_balance = 2
        self.employee.save()
        req = create_draft_leave_request(
            self.employee, self.regular_type, 'over balance', START, END,
        )
        with self.assertRaises(ValueError):
            req.submit()


class KedasyWorkflowTests(KedasyWorkflowMixin, WorkflowLeaveTypesMixin, TestCase):
    """Πλήρης ροή KEDASY και SDEY."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self._create_leave_types()
        self._set_balances(self.kedasy_employee, self.sdey_employee)

    @patch('weasyprint.HTML')
    def test_kedasy_employee_full_path_to_completed(self, _mock_html):
        req = create_draft_leave_request(
            self.kedasy_employee, self.regular_type, 'kedasy path', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'PENDING_KEDASY_PROTOCOL')

        self.client.force_login(self.kedasy_secretary)
        response = add_kedasy_protocol(self.client, req)
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'SUBMITTED')
        self.assertEqual(req.kedasy_kepea_protocol_number, 'KED-001')

        self.client.force_login(self.kedasy_manager)
        response = approve_leave_as_manager(self.client, req)
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'PENDING_PROTOCOL')

        self.client.force_login(self.leave_handler)
        advance_leave_to_in_review(self.client, req)
        response = complete_leave_as_handler(self.client, req, balance_after=20)
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'COMPLETED')

    @patch('weasyprint.HTML')
    def test_sdey_employee_approved_by_kedasy_manager(self, _mock_html):
        req = create_draft_leave_request(
            self.sdey_employee, self.regular_type, 'sdey path', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'PENDING_KEDASY_PROTOCOL')

        self.client.force_login(self.kedasy_secretary)
        add_kedasy_protocol(self.client, req, protocol_number='KED-SDEY-1')
        req.refresh_from_db()
        self.assertEqual(req.status, 'SUBMITTED')

        self.client.force_login(self.kedasy_manager)
        self.assertTrue(req.can_be_approved_by(self.kedasy_manager))
        approve_leave_as_manager(self.client, req)
        req.refresh_from_db()
        self.assertEqual(req.status, 'PENDING_PROTOCOL')
        self.assertEqual(req.manager_approved_by, self.kedasy_manager)

    @patch('weasyprint.HTML')
    def test_kedasy_no_approval_bypasses_manager_after_protocol(self, _mock_html):
        req = create_draft_leave_request(
            self.kedasy_employee, self.no_approval_type, 'kedasy no appr', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'PENDING_KEDASY_PROTOCOL')

        self.client.force_login(self.kedasy_secretary)
        add_kedasy_protocol(self.client, req, protocol_number='KED-NOAPP')
        req.refresh_from_db()
        self.assertEqual(req.status, 'PENDING_PROTOCOL')
        self.assertIsNone(req.manager_approved_by)

        self.client.force_login(self.leave_handler)
        advance_leave_to_in_review(self.client, req)
        complete_leave_as_handler(self.client, req, balance_after=25)
        req.refresh_from_db()
        self.assertEqual(req.status, 'COMPLETED')


class SimpleLeaveWorkflowTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Απλές άδειες — shortcut ολοκλήρωσης από προϊστάμενο."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self._create_leave_types()

    @patch('weasyprint.HTML')
    def test_simple_leave_completes_on_manager_approval(self, _mock_html):
        req = create_draft_leave_request(
            self.employee, self.simple_type, 'simple', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'SUBMITTED')

        self.client.force_login(self.dept_manager)
        approve_leave_as_manager(self.client, req)
        req.refresh_from_db()
        self.assertEqual(req.status, 'COMPLETED')
        self.assertEqual(req.processed_by, self.dept_manager)


class HandlerProtocolPathTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Ροή πρωτοκόλλου ΠΔΕΔΕ και επεξεργασίας."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self._create_leave_types()
        self._set_balances(self.employee)

    @patch('weasyprint.HTML')
    def test_full_protocol_path_in_review_then_complete(self, _mock_html):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'protocol path', START, END,
        )
        self.client.force_login(self.dept_manager)
        approve_leave_as_manager(self.client, req)
        req.refresh_from_db()
        self.assertEqual(req.status, 'PENDING_PROTOCOL')

        self.client.force_login(self.leave_handler)
        response = send_pdede_protocol(self.client, req)
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'IN_REVIEW')
        self.assertEqual(req.pdede_protocol_number, 'PDEDE-001')

        response = complete_leave_as_handler(self.client, req, balance_after=20)
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'COMPLETED')

    def test_handler_reject_from_pending_protocol(self):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'reject proto', START, END,
        )
        req.status = 'PENDING_PROTOCOL'
        req.manager_approved_by = self.dept_manager
        req.save()

        self.client.force_login(self.leave_handler)
        response = reject_leave_as_handler(self.client, req)
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'REJECTED_BY_LEAVES_DEPT')


class ApplicantWithdrawTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Ανακλήσεις από αιτούντα."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self._create_leave_types()

    def test_withdraw_from_submitted(self):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'withdraw', START, END,
        )
        self.client.force_login(self.employee)
        response = self.client.post(
            reverse('leaves:withdraw_leave_request', kwargs={'pk': req.pk}),
        )
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'CANCELLED_BY_APPLICANT')

    def test_withdraw_from_pending_kedasy_protocol(self):
        from accounts.models import DepartmentType

        kedasy_dt = DepartmentType.objects.create(name='ΚΕΔΑΣΥ Άλλο', code='KEDASY')
        kedasy_dept = Department.objects.create(
            name='ΚΕΔΑΣΥ Test',
            code='KEDASY_T2',
            department_type=kedasy_dt,
            headquarters=self.headquarters,
            prefecture=self.prefecture,
        )
        kedasy_user = User.objects.create_user(
            email='kedasy_w@test.com',
            first_name='K',
            last_name='W',
            department=kedasy_dept,
            registration_status='APPROVED',
            is_active=True,
        )
        kedasy_user.roles.add(self.employee_role)
        kedasy_user.current_regular_leave_balance = 25
        kedasy_user.save()

        req = create_draft_leave_request(
            kedasy_user, self.regular_type, 'kedasy withdraw', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'PENDING_KEDASY_PROTOCOL')

        self.client.force_login(kedasy_user)
        response = self.client.post(
            reverse('leaves:withdraw_leave_request', kwargs={'pk': req.pk}),
        )
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'CANCELLED_BY_APPLICANT')


class CompletedRevocationTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Ανάκληση ολοκληρωμένης άδειας (ολική / μερική) με ledger."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self._create_leave_types()
        self._set_balances(self.employee)

    def _completed_regular(self, days=5):
        from datetime import date, timedelta
        start = date(2025, 3, 3)
        end = start + timedelta(days=days - 1)
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'completed for revoke', start, end,
        )
        req.status = 'COMPLETED'
        req.completed_at = timezone.now()
        req.pdede_protocol_number = 'PDEDE-REV-1'
        req.save()
        from leaves.utils.balance_ledger import deduct_leave_days
        deduct_leave_days(
            employee=self.employee,
            days_used=days,
            leave_request=req,
            description='test deduct',
        )
        self.employee.refresh_from_db()
        return req

    def test_revoke_action_visible_on_completed(self):
        from leaves.dashboard_utils import get_available_actions

        req = self._completed_regular()
        codes = [code for code, _label, _url in get_available_actions(req, self.employee)]
        self.assertIn('revoke_leave', codes)

    def test_revocation_type_hidden_from_create_form(self):
        from leaves.forms import LeaveRequestForm

        form = LeaveRequestForm()
        ids = list(form.fields['leave_type'].queryset.values_list('id', flat=True))
        self.assertNotIn(self.revocation_type.id, ids)

    def test_create_total_revocation_and_complete_restores_balance(self):
        import json
        parent = self._completed_regular(days=5)
        balance_before = self.employee.current_regular_leave_balance

        self.client.force_login(self.employee)
        periods = [
            {
                'start_date': p.start_date.isoformat(),
                'end_date': p.end_date.isoformat(),
                'days': p.days,
            }
            for p in parent.periods.all()
        ]
        response = self.client.post(
            reverse('leaves:create_leave_revocation', kwargs={'pk': parent.pk}),
            {
                'revocation_scope': 'TOTAL',
                'days': 5,
                'periods_data': json.dumps(periods),
                'description': 'Ολική ανάκληση τεστ',
            },
        )
        self.assertEqual(response.status_code, 200)
        child = LeaveRequest.objects.filter(parent_leave=parent, leave_type__is_revocation=True).latest('id')
        self.assertEqual(child.status, 'DRAFT')
        self.assertEqual(child.revocation_scope, 'TOTAL')
        self.assertEqual(child.total_days, 5)

        child.status = 'IN_REVIEW'
        child.save(update_fields=['status'])
        self.assertTrue(child.complete_by_handler(self.leave_handler))

        child.refresh_from_db()
        parent.refresh_from_db()
        self.employee.refresh_from_db()

        self.assertEqual(child.status, 'COMPLETED')
        self.assertEqual(parent.status, 'REVOKED_BY_REQUEST')
        self.assertEqual(parent.revoked_days, 5)
        self.assertEqual(self.employee.current_regular_leave_balance, balance_before + 5)

        entry = RegularLeaveBalanceEntry.objects.filter(
            leave_request=child, entry_type='LEAVE_REVOKED',
        ).first()
        self.assertIsNotNone(entry)
        self.assertEqual(entry.days_delta, 5)

    def test_partial_revocation_keeps_parent_completed(self):
        import json
        from datetime import date, timedelta
        parent = self._completed_regular(days=5)
        balance_before = self.employee.current_regular_leave_balance
        start = date(2025, 3, 3)
        partial_end = start + timedelta(days=1)  # 2 days

        self.client.force_login(self.employee)
        response = self.client.post(
            reverse('leaves:create_leave_revocation', kwargs={'pk': parent.pk}),
            {
                'revocation_scope': 'PARTIAL',
                'days': 2,
                'periods_data': json.dumps([{
                    'start_date': start.isoformat(),
                    'end_date': partial_end.isoformat(),
                    'days': 2,
                }]),
                'description': 'Μερική ανάκληση τεστ',
            },
        )
        self.assertEqual(response.status_code, 200)
        child = LeaveRequest.objects.filter(parent_leave=parent).latest('id')
        child.status = 'IN_REVIEW'
        child.save(update_fields=['status'])
        self.assertTrue(child.complete_by_handler(self.leave_handler))

        parent.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertEqual(parent.status, 'COMPLETED')
        self.assertEqual(parent.revoked_days, 2)
        self.assertEqual(parent.remaining_revocable_days, 3)
        self.assertEqual(self.employee.current_regular_leave_balance, balance_before + 2)

    def test_open_revocation_blocks_second(self):
        import json
        parent = self._completed_regular(days=3)
        self.client.force_login(self.employee)
        periods = [{
            'start_date': p.start_date.isoformat(),
            'end_date': p.end_date.isoformat(),
            'days': p.days,
        } for p in parent.periods.all()]
        self.client.post(
            reverse('leaves:create_leave_revocation', kwargs={'pk': parent.pk}),
            {
                'revocation_scope': 'TOTAL',
                'days': 3,
                'periods_data': json.dumps(periods),
                'description': 'first',
            },
        )
        parent.refresh_from_db()
        self.assertFalse(parent.can_request_leave_revocation(self.employee))

    def test_withdraw_completed_redirects_to_revoke(self):
        parent = self._completed_regular()
        self.client.force_login(self.employee)
        response = self.client.get(
            reverse('leaves:withdraw_completed_leave', kwargs={'pk': parent.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/revoke/', response.url)


class DocumentsWorkflowTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Κύκλος δικαιολογητικών."""

    def setUp(self):
        super().setUp()
        self._create_leave_types()

    def test_documents_request_and_provide_loop(self):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'docs', START, END,
        )
        req.status = 'IN_REVIEW'
        req.save()

        req.request_documents(self.leave_handler, 'Βεβαίωση ιατρού')
        req.refresh_from_db()
        self.assertEqual(req.status, 'WAITING_FOR_DOCUMENTS')

        req.provide_documents(self.leave_handler, 'Παραλήφθηκαν')
        req.refresh_from_db()
        self.assertEqual(req.status, 'IN_REVIEW')

    def test_applicant_can_upload_attachment_while_waiting_documents(self):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'docs upload', START, END,
        )
        req.status = 'IN_REVIEW'
        req.save()
        req.request_documents(self.leave_handler, 'Βεβαίωση ιατρού')
        req.refresh_from_db()

        self.assertTrue(req.can_user_upload_attachment(self.employee))
        self.assertFalse(req.can_user_upload_attachment(self.dept_manager))

        from leaves.dashboard_utils import get_available_actions
        codes = [code for code, _label, _url in get_available_actions(req, self.employee)]
        self.assertIn('upload_attachment', codes)

    def test_decision_after_documents_provided_despite_sick_threshold(self):
        """Μετά παροχή δικαιολογητικών, η αίτηση προχωρά σε απόφαση — όχι ξανά σε ΥΕ."""
        from leaves.dashboard_utils import get_available_actions

        prior = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'prior sick', '2025-01-06', '2025-01-10',
        )
        prior.status = 'COMPLETED'
        prior.submitted_at = timezone.now()
        prior.save()

        req = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'sick docs', '2025-03-03', '2025-03-14',
        )
        req.status = 'IN_REVIEW'
        req.submitted_at = timezone.now()
        req.save()

        self.assertTrue(req.can_send_to_yc)
        req.request_documents(self.leave_handler, 'Γνωμάτευση')
        req.provide_documents(self.leave_handler, 'Ελήφθη')
        req.refresh_from_db()

        self.assertFalse(req.can_send_to_yc)
        codes = [code for code, _label, _url in get_available_actions(req, self.leave_handler)]
        self.assertIn('decision', codes)
        self.assertNotIn('yc_referral', codes)


class DecisionPathModelTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """ΣΗΔΕ path μέσω model transitions."""

    def setUp(self):
        super().setUp()
        self._create_leave_types()

    def test_decision_preparation_to_signatures(self):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'decision', START, END,
        )
        req.status = 'IN_REVIEW'
        req.save()

        self.assertTrue(req.start_decision_preparation(self.leave_handler))
        req.refresh_from_db()
        self.assertEqual(req.status, 'DECISION_PREPARATION')

        self.assertTrue(req.send_to_signatures(self.leave_handler))
        req.refresh_from_db()
        self.assertEqual(req.status, 'PENDING_SIGNATURES')


class BalanceIntegrityTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Υπόλοιπα — δεν χάνονται ημέρες σε απόρριψη/ανάκληση."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self._create_leave_types()
        self._set_balances(self.employee)

    @patch('weasyprint.HTML')
    def test_balance_deducted_once_on_completion(self, _mock_html):
        initial_entries = RegularLeaveBalanceEntry.objects.filter(employee=self.employee).count()
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'balance', START, END,
        )

        self.client.force_login(self.dept_manager)
        approve_leave_as_manager(self.client, req)
        req.refresh_from_db()

        self.client.force_login(self.leave_handler)
        advance_leave_to_in_review(self.client, req)
        complete_leave_as_handler(self.client, req, balance_after=20)
        req.refresh_from_db()

        self.assertEqual(req.status, 'COMPLETED')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.current_regular_leave_balance, 20)
        self.assertEqual(
            RegularLeaveBalanceEntry.objects.filter(employee=self.employee).count(),
            initial_entries + 1,
        )
        self.assertEqual(get_last_balance(self.employee), 20)

    def test_balance_not_deducted_on_manager_reject(self):
        self._set_balances(self.employee, balance=25)
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'no deduct reject', START, END,
        )
        req.reject_by_manager(self.dept_manager, 'Όχι')
        req.refresh_from_db()

        self.employee.refresh_from_db()
        self.assertEqual(self.employee.current_regular_leave_balance, 25)
        self.assertEqual(req.status, 'SUPERVISOR_REJECTED')


class SickLeaveWorkflowTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Αναρρωτικές — όρια και Υγειονομική Επιτροπή."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self._create_leave_types()
        self.employee.sick_leave_with_declaration = 2
        self.employee.save()

    def test_sick_yd_limit_blocks_third_submit(self):
        for i in range(2):
            req = create_draft_leave_request(
                self.employee, self.sick_yd_type, f'sick {i}', START, END,
            )
            submit_leave_request(req)
            req.status = 'COMPLETED'
            req.save()

        req = create_draft_leave_request(
            self.employee, self.sick_yd_type, 'sick over limit', START, END,
        )
        with self.assertRaises(ValueError):
            req.submit()

    def test_yc_committee_round_trip(self):
        req = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'yc', '2025-03-03', '2025-03-14',
        )
        req.status = 'IN_REVIEW'
        req.submitted_at = timezone.now()
        req.save()

        # Δεύτερη αναρρωτική στο ίδιο έτος για να ξεπεράσει το όριο 8 ημερών
        prior = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'prior sick', '2025-01-06', '2025-01-10',
        )
        prior.status = 'COMPLETED'
        prior.submitted_at = timezone.now()
        prior.save()

        self.assertTrue(req.can_send_to_yc)
        req.send_to_yc_committee(self.leave_handler)
        req.refresh_from_db()
        self.assertEqual(req.status, 'PENDING_YC_COMMITTEE')

        req.receive_from_yc_committee(self.leave_handler)
        req.refresh_from_db()
        self.assertEqual(req.status, 'IN_REVIEW')
        self.assertTrue(req.has_returned_from_yc_committee)
        self.assertFalse(req.can_send_to_yc)
        self.assertTrue(req.can_create_decision())

    def _seed_sick_threshold_exceeded(self):
        """Ολοκληρωμένη αναρρωτική >8 ημερών ώστε να ενεργοποιηθεί το όριο ΥΕ."""
        prior = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'prior sick', '2025-01-06', '2025-01-10',
        )
        prior.status = 'COMPLETED'
        prior.submitted_at = timezone.now()
        prior.save()

    def test_yc_referral_only_for_sick_total_type(self):
        """Κανονική ή βραχυχρόνια αναρρωτική δεν πηγαίνουν σε ΥΕ λόγω άλλων αιτήσεων."""
        self._seed_sick_threshold_exceeded()

        for leave_type in (self.regular_type, self.sick_yd_type):
            with self.subTest(leave_type=leave_type.code):
                req = create_submitted_leave_request(
                    self.employee, leave_type, f'other {leave_type.code}', START, END,
                )
                req.status = 'IN_REVIEW'
                req.submitted_at = timezone.now()
                req.save()
                self.assertFalse(req.can_send_to_yc)
                self.assertTrue(req.can_create_decision())

    def test_second_sick_leave_shows_decision_while_first_pending_yc(self):
        """Δεύτερη αναρρωτική σε IN_REVIEW: διαθέσιμα και ΥΕ και ετοιμασία απόφασης."""
        from leaves.dashboard_utils import get_available_actions

        self._seed_sick_threshold_exceeded()

        first = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'first sick yc', '2025-02-03', '2025-02-07',
        )
        first.status = 'PENDING_YC_COMMITTEE'
        first.submitted_at = timezone.now()
        first.save()

        second = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'second sick', '2025-03-03', '2025-03-07',
        )
        second.status = 'IN_REVIEW'
        second.submitted_at = timezone.now()
        second.save()

        self.assertTrue(second.can_send_to_yc)
        codes = [code for code, _label, _url in get_available_actions(second, self.leave_handler)]
        self.assertIn('yc_referral', codes)
        self.assertIn('decision', codes)

    def test_yc_round_trip_allows_decision_action(self):
        """Μετά την επιστροφή από ΥΕ εμφανίζεται ετοιμασία απόφασης, όχι νέο διαβιβαστικό."""
        from leaves.dashboard_utils import get_available_actions

        self._seed_sick_threshold_exceeded()
        req = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'yc decision', '2025-03-03', '2025-03-14',
        )
        req.status = 'IN_REVIEW'
        req.submitted_at = timezone.now()
        req.save()

        req.send_to_yc_committee(self.leave_handler)
        req.receive_from_yc_committee(self.leave_handler)
        req.refresh_from_db()

        codes = [code for code, _label, _url in get_available_actions(req, self.leave_handler)]
        self.assertIn('decision', codes)
        self.assertNotIn('yc_referral', codes)


class KnownIssueRegressionTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Regression tests για διορθώσεις workflow bugs."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self._create_leave_types()

    def test_handler_reject_from_decision_preparation(self):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'reject decision', START, END,
        )
        req.status = 'DECISION_PREPARATION'
        req.save()

        self.client.force_login(self.leave_handler)
        response = reject_leave_as_handler(self.client, req, reason='Λάθος απόφαση')
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'REJECTED_BY_LEAVES_DEPT')

    def test_handler_reject_from_pending_signatures(self):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'reject signatures', START, END,
        )
        req.status = 'PENDING_SIGNATURES'
        req.save()

        self.client.force_login(self.leave_handler)
        reject_leave_as_handler(self.client, req, reason='Ακυρώθηκε ΣΗΔΕ')
        req.refresh_from_db()
        self.assertEqual(req.status, 'REJECTED_BY_LEAVES_DEPT')

    def test_withdraw_completed_redirects_to_revoke_flow(self):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'revoke notify', START, END,
        )
        req.status = 'COMPLETED'
        req.save()

        self.client.force_login(self.employee)
        response = self.client.get(
            reverse('leaves:withdraw_completed_leave', kwargs={'pk': req.pk}),
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/revoke/{req.pk}/', response.url)
        req.refresh_from_db()
        self.assertEqual(req.status, 'COMPLETED')

    def test_sick_total_counted_once_on_handler_complete(self):
        req = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'single sick count', START, END,
        )
        req.status = 'PENDING_PROTOCOL'
        req.submitted_at = timezone.now()
        req.save()

        self.client.force_login(self.leave_handler)
        advance_leave_to_in_review(self.client, req)
        complete_leave_as_handler(self.client, req, balance_after=25)

        yearly = YearlySickLeaveTotal.objects.get(
            employee=self.employee,
            year=timezone.now().year,
        )
        self.employee.refresh_from_db()
        self.assertEqual(yearly.total_days, req.total_days)
        self.assertEqual(self.employee.sick_days_current_year, req.total_days)
        self.assertEqual(self.employee.total_sick_leave_last_5_years, req.total_days)

    def test_sick_5yr_cache_includes_prior_years_excludes_year_6(self):
        cy = timezone.now().year
        YearlySickLeaveTotal.objects.create(employee=self.employee, year=cy - 6, total_days=50)
        YearlySickLeaveTotal.objects.create(employee=self.employee, year=cy - 1, total_days=4)

        req = create_submitted_leave_request(
            self.employee, self.sick_total_type, 'sick window', START, END,
        )
        req.status = 'IN_REVIEW'
        req.submitted_at = timezone.now()
        req.save()
        self.assertTrue(req.complete_by_handler(self.leave_handler))

        self.employee.refresh_from_db()
        # year-6 (50) excluded; year-1 (4) + current (5) = 9
        self.assertEqual(self.employee.total_sick_leave_last_5_years, 4 + req.total_days)
        self.assertTrue(
            YearlySickLeaveTotal.objects.filter(employee=self.employee, year=cy - 6).exists()
        )


class WorkflowVariantRoutingTests(KedasyWorkflowMixin, WorkflowLeaveTypesMixin, TestCase):
    """Έλεγχος ότι το workflow_variant επηρεάζει τη δρομολόγηση."""

    def setUp(self):
        super().setUp()
        self._create_leave_types()
        self._set_balances(self.employee, self.kedasy_employee, self.sdey_employee)
        self.kedasy_leave_type = LeaveType.objects.create(
            name='Άδεια KEDASY variant',
            code='WF_KEDASY_VAR',
            workflow_variant='KEDASY',
            requires_approval=True,
            affects_regular_leave_balance=True,
        )
        self.sdey_leave_type = LeaveType.objects.create(
            name='Άδεια SDEY variant',
            code='WF_SDEY_VAR',
            workflow_variant='SDEY',
            requires_approval=True,
        )

    def test_kedasy_variant_on_pedagogical_department_submits_to_manager(self):
        req = create_draft_leave_request(
            self.employee, self.kedasy_leave_type, 'std dept', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'SUBMITTED')

    def test_kedasy_variant_on_kedasy_department_needs_protocol(self):
        req = create_draft_leave_request(
            self.kedasy_employee, self.kedasy_leave_type, 'kedasy dept', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'PENDING_KEDASY_PROTOCOL')

    def test_sdey_variant_on_sdey_department_needs_protocol(self):
        req = create_draft_leave_request(
            self.sdey_employee, self.sdey_leave_type, 'sdey dept', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'PENDING_KEDASY_PROTOCOL')

    def test_sdey_variant_on_pedagogical_department_uses_standard_path(self):
        req = create_draft_leave_request(
            self.employee, self.sdey_leave_type, 'wrong dept', START, END,
        )
        submit_leave_request(req)
        self.assertEqual(req.status, 'SUBMITTED')


class HandlerCompletionGuardTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Δεν επιτρέπεται ολοκλήρωση χωρίς IN_REVIEW."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self._create_leave_types()
        self._set_balances(self.employee)

    @patch('weasyprint.HTML')
    def test_cannot_complete_directly_from_pending_protocol(self, _mock_html):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'no shortcut', START, END,
        )
        req.status = 'PENDING_PROTOCOL'
        req.save()

        self.client.force_login(self.leave_handler)
        response = complete_leave_as_handler(self.client, req, balance_after=20)
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'PENDING_PROTOCOL')

    def test_model_rejects_complete_from_pending_protocol(self):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'model guard', START, END,
        )
        req.status = 'PENDING_PROTOCOL'
        req.save()
        self.assertFalse(req.complete_by_handler(self.leave_handler))


class SidEHttpFlowTests(TestDataMixin, WorkflowLeaveTypesMixin, TestCase):
    """Πλήρης HTTP ροή ΣΗΔΕ: πρωτόκολλο → απόφαση → υπογραφές → ακριβές αντίγραφο."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self._create_leave_types()
        self._set_balances(self.employee)

    @patch('weasyprint.HTML')
    @patch('leaves.decision_views.SecureFileHandler')
    def test_full_side_flow_completes_via_exact_copy(self, mock_handler_cls, _mock_html):
        mock_handler = mock_handler_cls.return_value
        mock_handler.save_encrypted_bytes.return_value = ('media/test/exact.pdf', 'abc123')

        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'side flow', START, END,
        )
        self.client.force_login(self.dept_manager)
        approve_leave_as_manager(self.client, req)
        req.refresh_from_db()

        self.client.force_login(self.leave_handler)
        advance_leave_to_in_review(self.client, req)
        req.refresh_from_db()
        self.assertEqual(req.status, 'IN_REVIEW')

        req.decision_pdf_path = 'media/test/decision.pdf'
        req.decision_pdf_encryption_key = 'def456'
        req.start_decision_preparation(self.leave_handler)
        req.send_to_signatures(self.leave_handler)
        req.refresh_from_db()
        self.assertEqual(req.status, 'PENDING_SIGNATURES')

        from django.core.files.uploadedfile import SimpleUploadedFile
        pdf_file = SimpleUploadedFile('exact.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        response = self.client.post(
            reverse('leaves:upload_exact_copy_pdf', kwargs={'pk': req.pk}),
            {'exact_copy_pdf': pdf_file},
        )
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertTrue(req.has_exact_copy_pdf())

        response = self.client.post(
            reverse('leaves:complete_leave_request_final', kwargs={'pk': req.pk}),
        )
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.status, 'COMPLETED')
        self.assertEqual(req.processed_by, self.leave_handler)
