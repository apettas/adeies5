"""Tests για ενιαία εμφάνιση ενεργειών dashboard / προβολής."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from accounts.tests.test_data import TestDataMixin
from leaves.dashboard_utils import get_available_actions
from leaves.models import LeavePeriod, LeaveRequest, LeaveType

User = get_user_model()


class DashboardActionsTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.leave_type = LeaveType.objects.create(
            name='Κανονική',
            code='ACT_ANNUAL',
            requires_approval=True,
            affects_regular_leave_balance=True,
        )

    def _create_request(self, status):
        req = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            description='actions test',
            status=status,
            submitted_at=timezone.now(),
        )
        LeavePeriod.objects.create(
            leave_request=req,
            start_date='2025-04-01',
            end_date='2025-04-05',
        )
        return req

    def _codes(self, leave_request, user):
        return [code for code, _label, _url in get_available_actions(leave_request, user)]

    def test_handler_pending_protocol_actions(self):
        req = self._create_request('PENDING_PROTOCOL')
        codes = self._codes(req, self.leave_handler)
        self.assertIn('protocol', codes)
        self.assertIn('send_protocol_pdf', codes)
        self.assertIn('reject', codes)
        self.assertNotIn('complete', codes)
        self.assertNotIn('decision', codes)

    def test_handler_in_review_actions(self):
        req = self._create_request('IN_REVIEW')
        codes = self._codes(req, self.leave_handler)
        self.assertIn('request_documents', codes)
        self.assertIn('return', codes)
        self.assertIn('decision', codes)
        self.assertIn('complete', codes)
        self.assertNotIn('protocol', codes)
        self.assertNotIn('upload_final', codes)

    def test_handler_pending_signatures_requires_exact_copy_for_complete(self):
        req = self._create_request('PENDING_SIGNATURES')
        req.decision_pdf_path = 'media/test/decision.pdf'
        req.decision_pdf_encryption_key = 'abc'
        req.save()
        codes = self._codes(req, self.leave_handler)
        self.assertIn('edit_decision', codes)
        self.assertIn('upload_final', codes)
        self.assertNotIn('complete', codes)

        req.exact_copy_pdf_path = 'media/test/exact.pdf'
        req.exact_copy_pdf_encryption_key = 'def'
        req.save()
        codes = self._codes(req, self.leave_handler)
        self.assertIn('complete', codes)

    def test_handler_pending_yc_committee_no_shortcut_complete(self):
        req = self._create_request('PENDING_YC_COMMITTEE')
        codes = self._codes(req, self.leave_handler)
        self.assertIn('upload_docs', codes)
        self.assertNotIn('complete', codes)
        self.assertNotIn('decision', codes)

    def test_manager_submitted_actions(self):
        req = self._create_request('SUBMITTED')
        codes = self._codes(req, self.dept_manager)
        self.assertIn('approve', codes)
        self.assertIn('reject', codes)
        self.assertNotIn('protocol', codes)

    def test_owner_withdraw_only_when_allowed(self):
        req = self._create_request('SUBMITTED')
        self.assertIn('cancel', self._codes(req, self.employee))

        req.status = 'PENDING_PROTOCOL'
        req.save()
        self.assertNotIn('cancel', self._codes(req, self.employee))

    def test_completed_handler_only_view(self):
        req = self._create_request('COMPLETED')
        codes = self._codes(req, self.leave_handler)
        self.assertEqual(codes, ['view'])

    def test_list_and_detail_share_same_action_codes(self):
        req = self._create_request('IN_REVIEW')
        list_codes = self._codes(req, self.leave_handler)
        detail_codes = [
            code for code in list_codes if code != 'view'
        ]
        self.assertIn('request_documents', detail_codes)
        self.assertIn('return', detail_codes)
        self.assertIn('complete', detail_codes)
