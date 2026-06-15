from django.test import TestCase

from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveRequest, LeaveType
from leaves.templatetags.leave_pdf_tags import (
    build_default_request_body_text,
    resolve_request_body_text,
)


class LeaveRequestPdfTextTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.leave_type = LeaveType.objects.create(
            name='Άδεια Γάμου',
            subject_text='Χορήγηση άδειας γάμου',
            decision_text='άδεια γάμου',
            requires_approval=True,
        )
        self.leave_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            status='SUBMITTED',
        )

    def test_default_body_uses_decision_text(self):
        self.assertEqual(
            build_default_request_body_text(self.leave_request),
            'Παρακαλώ να μου χορηγήσετε άδεια γάμου για τα κάτωθι χρονικά διαστήματα:',
        )

    def test_legacy_override_is_replaced(self):
        legacy = (
            'Παρακαλώ να μου χορηγήσετε άδεια Άδεια Γάμου '
            'για τα κάτωθι χρονικά διαστήματα:'
        )
        resolved = resolve_request_body_text(self.leave_request, legacy)
        self.assertEqual(
            resolved,
            'Παρακαλώ να μου χορηγήσετε άδεια γάμου για τα κάτωθι χρονικά διαστήματα:',
        )
