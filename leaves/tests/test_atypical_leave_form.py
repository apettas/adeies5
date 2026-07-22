"""Tests για άτυπες άδειες (create-atypical)."""
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from accounts.tests.test_data import TestDataMixin
from leaves.forms import LeaveRequestForm, AtypicalLeaveForm
from leaves.models import LeaveType
from leaves.tests.helpers import create_submitted_leave_request


class AtypicalLeaveFormPageTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.child_department.has_atypical_leaves = True
        self.child_department.save(update_fields=['has_atypical_leaves'])
        self.employee.department = self.child_department
        self.employee.save(update_fields=['department'])
        self.atypical_type = LeaveType.objects.create(
            name='Προφορική Test',
            code='TEST_ATYPICAL',
            requires_approval=True,
            is_simple=True,
            is_active=True,
            affects_regular_leave_balance=False,
        )
        self.regular_type = LeaveType.objects.create(
            name='Κανονική Test',
            code='TEST_REGULAR_ATYP',
            requires_approval=True,
            is_simple=False,
            is_active=True,
        )

    def test_atypical_page_renders_period_and_buttons(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse('leaves:create_atypical_leave'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="periods-container"')
        self.assertContains(response, 'period-card')
        self.assertContains(response, 'id="add-period-btn"')
        self.assertContains(response, 'id="add-attachment-btn"')
        self.assertContains(response, 'id="attachment-groups"')
        self.assertContains(response, self.atypical_type.name)

    def test_anonymous_redirects_not_attribute_error(self):
        response = self.client.get(reverse('leaves:create_atypical_leave'))
        self.assertEqual(response.status_code, 302)

    def test_regular_form_excludes_simple_types(self):
        form = LeaveRequestForm()
        ids = set(form.fields['leave_type'].queryset.values_list('id', flat=True))
        self.assertIn(self.regular_type.id, ids)
        self.assertNotIn(self.atypical_type.id, ids)

    def test_atypical_form_only_simple_types(self):
        form = AtypicalLeaveForm()
        ids = set(form.fields['leave_type'].queryset.values_list('id', flat=True))
        self.assertIn(self.atypical_type.id, ids)
        self.assertNotIn(self.regular_type.id, ids)

    @patch('pdede_leaves.email_utils.send_merged_pdf_email')
    @patch('leaves.utils.pdf_merger.save_merged_pdf', return_value=(b'%PDF', 'x', 'y'))
    def test_submit_final_skips_email_for_simple_leave(self, mock_save, mock_email):
        req = create_submitted_leave_request(
            self.employee, self.atypical_type, 'atypical', '2026-07-01', '2026-07-01',
        )
        req.status = 'DRAFT'
        req.save(update_fields=['status'])
        self.client.force_login(self.employee)
        response = self.client.post(
            reverse('leaves:submit_final_request'),
            {'leave_request_id': req.pk, 'description': 'test'},
        )
        self.assertEqual(response.status_code, 302)
        mock_email.assert_not_called()
