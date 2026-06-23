"""Tests για workflow εκκρεμών εγγραφών χρηστών (χειριστής αδειών)."""
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import (
    EmployeeType,
    Headquarters,
    PendingRegistrationAcknowledgment,
    Prefecture,
    Role,
    Specialty,
    User,
)
from accounts.tests.test_data import TestDataMixin
from accounts.utils.pending_registration_alerts import (
    get_pending_registration_alerts,
    mark_registration_submitted,
)


class PendingRegistrationWorkflowTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.employee_type, _ = EmployeeType.objects.get_or_create(
            code='EDUCATIONAL',
            defaults={'name': 'Εκπαιδευτικοί'},
        )
        self.specialty = Specialty.objects.create(
            specialties_short='ΠΕ02',
            specialties_full='ΠΕ02 Μαθηματικών',
        )
        self.pending_user = User.objects.create_user(
            email='pending@test.com',
            first_name='νέος',
            last_name='χρήστης',
            password='testpass123',
            department=self.child_department,
            specialty=self.specialty,
            registration_status='PENDING',
            is_active=False,
            employee_number='EMP999',
        )
        mark_registration_submitted(self.pending_user)
        self.client.force_login(self.leave_handler)

    def test_handler_sees_pending_list(self):
        response = self.client.get(reverse('leaves:pending_user_registrations'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'pending@test.com')
        self.assertContains(response, 'νέος')

    def test_review_form_shows_editable_role_description(self):
        self.pending_user.role_description = 'Αναπληρωτής'
        self.pending_user.save(update_fields=['role_description'])
        response = self.client.get(
            reverse('leaves:pending_user_registration_review', args=[self.pending_user.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Υπηρεσιακή Ιδιότητα')
        self.assertContains(response, 'name="role_description"')
        self.assertContains(response, 'Αναπληρωτής')

    def test_review_form_defaults_to_employee_role(self):
        response = self.client.get(
            reverse('leaves:pending_user_registration_review', args=[self.pending_user.pk]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'value="{self.employee_role.pk}" selected')

    def test_alert_visible_until_acknowledged(self):
        alerts = get_pending_registration_alerts(self.leave_handler)
        self.assertEqual(alerts.count(), 1)

        response = self.client.get(reverse('leaves:handler_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Νέες Εγγραφές Χρηστών')
        self.assertContains(response, 'pending@test.com')

    def test_acknowledge_hides_alert_for_handler(self):
        self.client.get(reverse('leaves:acknowledge_pending_registration', args=[self.pending_user.pk]))
        alerts = get_pending_registration_alerts(self.leave_handler)
        self.assertEqual(alerts.count(), 0)

        response = self.client.get(reverse('leaves:handler_dashboard'))
        self.assertNotContains(response, 'pending@test.com')

    def test_activate_user_sends_approval_and_removes_from_pending(self):
        from unittest.mock import patch

        review_url = reverse(
            'leaves:pending_user_registration_review',
            args=[self.pending_user.pk],
        )
        with patch('pdede_leaves.email_utils.send_registration_approved_email') as mock_email:
            with patch('pdede_leaves.email_utils.send_registration_approved_notification'):
                response = self.client.post(review_url, {
                    'first_name': self.pending_user.first_name,
                    'last_name': self.pending_user.last_name,
                    'name_accusative': '',
                    'father_name': '',
                    'gender': '',
                    'phone1': '',
                    'employee_number': self.pending_user.employee_number,
                    'gsn_branch': '',
                    'sso_organizational_unit': '',
                    'role_description': 'Εκπαιδευτικός',
                    'department': self.child_department.pk,
                    'specialty': self.specialty.pk,
                    'employee_type': self.employee_type.pk,
                    'roles': [self.employee_role.pk],
                    'notification_recipients': '',
                    'annual_leave_entitlement': 25,
                    'current_regular_leave_balance': 25,
                    'can_request_leave': True,
                    'approval_notes': 'OK',
                    'action': 'activate',
                })
        self.assertEqual(response.status_code, 302)
        self.pending_user.refresh_from_db()
        self.assertEqual(self.pending_user.registration_status, 'APPROVED')
        self.assertTrue(self.pending_user.is_active)
        self.assertEqual(self.pending_user.approved_by, self.leave_handler)
        mock_email.assert_called_once()

        from accounts.utils.pending_registration_alerts import get_pending_registrations_queryset
        self.assertEqual(get_pending_registrations_queryset().filter(pk=self.pending_user.pk).count(), 0)

    def test_non_handler_denied(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse('leaves:pending_user_registrations'))
        self.assertEqual(response.status_code, 403)

    def test_resubmit_resets_acknowledgments(self):
        PendingRegistrationAcknowledgment.objects.create(
            handler=self.leave_handler,
            pending_user=self.pending_user,
        )
        mark_registration_submitted(self.pending_user)
        alerts = get_pending_registration_alerts(self.leave_handler)
        self.assertEqual(alerts.count(), 1)

    def test_reject_deletes_pending_user(self):
        user_id = self.pending_user.pk
        response = self.client.post(reverse('leaves:reject_pending_registration', args=[user_id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertEqual(
            get_pending_registration_alerts(self.leave_handler).count(),
            0,
        )

    def test_handler_can_edit_registration_email_template(self):
        response = self.client.get(reverse('leaves:registration_approval_email_template'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Πρότυπο Email Ενεργοποίησης')
        self.assertContains(response, '{full_name}')

    def test_save_registration_email_template(self):
        custom_body = 'Γεια σας {full_name}, ενεργοποιήθηκε ο λογαριασμός σας.'
        response = self.client.post(
            reverse('leaves:registration_approval_email_template'),
            data={
                'subject': 'Νέο θέμα ενεργοποίησης',
                'body': custom_body,
            },
        )
        self.assertEqual(response.status_code, 302)
        from accounts.utils.registration_email import get_registration_approval_email_template
        template = get_registration_approval_email_template()
        self.assertEqual(template.subject, 'Νέο θέμα ενεργοποίησης')
        self.assertEqual(template.body, custom_body)
        self.assertEqual(template.updated_by, self.leave_handler)
