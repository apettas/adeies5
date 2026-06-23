"""Tests για email δικαιολογητικών και alerts ανεβάσματος από αιτούντα."""
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from accounts.tests.test_data import TestDataMixin
from leaves.models import DocumentUploadAcknowledgment, LeaveType
from leaves.tests.helpers import create_submitted_leave_request
from leaves.utils.document_upload_alerts import (
    get_pending_document_upload_alerts,
    mark_applicant_document_uploaded,
)

START = '2025-03-03'
END = '2025-03-07'


class DocumentNotificationTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.regular_type = LeaveType.objects.create(
            name='Κανονική Άδεια',
            code='DOC_TEST_ANNUAL',
            requires_approval=True,
            affects_regular_leave_balance=True,
        )
        self.client = Client()

    def _waiting_request(self):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'docs email', START, END,
        )
        req.status = 'IN_REVIEW'
        req.save()
        req.request_documents(self.leave_handler, 'Βεβαίωση ιατρού')
        req.refresh_from_db()
        return req

    @patch('pdede_leaves.email_utils.send_documents_required_email', return_value=True)
    def test_request_documents_sends_email_to_editable_address(self, mock_send_email):
        req = create_submitted_leave_request(
            self.employee, self.regular_type, 'docs email post', START, END,
        )
        req.status = 'IN_REVIEW'
        req.save()

        self.client.force_login(self.leave_handler)
        response = self.client.post(
            reverse('leaves:request_documents', kwargs={'pk': req.pk}),
            {
                'required_documents': 'Ιατρική βεβαίωση',
                'notification_email': 'custom@example.com',
            },
        )
        self.assertEqual(response.status_code, 302)
        req.refresh_from_db()
        self.assertEqual(req.documents_notification_email, 'custom@example.com')
        mock_send_email.assert_called_once()
        self.assertEqual(mock_send_email.call_args.args[1], 'custom@example.com')

    def test_applicant_upload_shows_handler_alert_until_acknowledged(self):
        req = self._waiting_request()
        mark_applicant_document_uploaded(req)

        alerts = list(get_pending_document_upload_alerts(self.leave_handler))
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].pk, req.pk)

        self.client.force_login(self.leave_handler)
        response = self.client.get(reverse('leaves:acknowledge_document_upload', kwargs={'pk': req.pk}))
        self.assertRedirects(response, reverse('leaves:handler_dashboard'))
        self.assertEqual(list(get_pending_document_upload_alerts(self.leave_handler)), [])

    def test_new_applicant_upload_resets_acknowledgment(self):
        req = self._waiting_request()
        mark_applicant_document_uploaded(req)
        DocumentUploadAcknowledgment.objects.create(
            leave_request=req,
            handler=self.leave_handler,
        )
        self.assertEqual(list(get_pending_document_upload_alerts(self.leave_handler)), [])

        mark_applicant_document_uploaded(req)
        self.assertEqual(len(get_pending_document_upload_alerts(self.leave_handler)), 1)
