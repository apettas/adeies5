"""Tests για τη διαχείριση βασικών στοιχείων (/leaves/base-data/)."""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model

from accounts.models import Role
from accounts.tests.test_data import TestDataMixin
from leaves.base_data_config import build_field_specs, get_table_config, TABLE_REGISTRY
from leaves.models import LeaveType, PublicHoliday

User = get_user_model()


class BaseDataConfigTests(TestCase):
    def test_all_tables_have_models(self):
        for key, cfg in TABLE_REGISTRY.items():
            self.assertIsNotNone(cfg['model'], key)

    def test_user_field_specs_include_department_and_roles(self):
        model_class, config = get_table_config('users')
        specs = build_field_specs(model_class, config)
        names = {s['name'] for s in specs}
        self.assertIn('department', names)
        self.assertIn('roles', names)
        self.assertIn('annual_leave_entitlement', names)
        self.assertNotIn('password', names)

    def test_leave_type_includes_workflow_variant(self):
        model_class, config = get_table_config('leave_types')
        specs = build_field_specs(model_class, config)
        wf = next(s for s in specs if s['name'] == 'workflow_variant')
        self.assertEqual(wf['widget'], 'select')
        self.assertTrue(wf['choices'])


class BaseDataViewTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.handler_role, _ = Role.objects.get_or_create(
            code='LEAVE_HANDLER',
            defaults={'name': 'Χειριστής Αδειών', 'is_active': True},
        )
        self.handler = User.objects.create_user(
            email='handler@example.com',
            first_name='Handler',
            last_name='User',
            password='testpass123',
            department=self.autotelous_dn,
            registration_status='APPROVED',
            is_active=True,
        )
        self.handler.roles.add(self.handler_role)

    def test_index_requires_permission(self):
        response = self.client.get(reverse('leaves:base_data_index'))
        self.assertEqual(response.status_code, 302)

    def test_handler_can_access_index(self):
        self.client.force_login(self.handler)
        response = self.client.get(reverse('leaves:base_data_index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Τμήματα')
        self.assertContains(response, 'Δημόσιες Αργίες')

    def test_handler_can_edit_leave_type(self):
        leave_type = LeaveType.objects.create(
            code='TEST_LEAVE',
            name='Δοκιμαστική Άδεια',
            workflow_variant='STANDARD',
            decision_text='',
            subject_text='',
        )
        self.client.force_login(self.handler)
        response = self.client.post(
            reverse('leaves:base_data_table', kwargs={'table_key': 'leave_types'}),
            {
                'action': 'edit',
                'record_id': leave_type.pk,
                'code': 'TEST_LEAVE',
                'name': 'Ενημερωμένη Άδεια',
                'workflow_variant': 'KEDASY',
                'requires_approval': 'True',
                'is_active': 'True',
                'affects_regular_leave_balance': 'True',
                'is_simple': 'False',
                'is_sick_leave_yd': 'False',
                'is_sick_leave_total': 'False',
                'is_revocation': 'False',
                'subject_text': '',
                'decision_text': '',
                'instructions': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        leave_type.refresh_from_db()
        self.assertEqual(leave_type.name, 'Ενημερωμένη Άδεια')
        self.assertEqual(leave_type.workflow_variant, 'KEDASY')

    def test_get_record_data_includes_fk_fields(self):
        self.client.force_login(self.handler)
        url = reverse(
            'leaves:get_record_data',
            kwargs={'table_key': 'users', 'record_id': self.handler.pk},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('department', data)
        self.assertIn('roles', data)

    def test_public_holiday_crud(self):
        self.client.force_login(self.handler)
        add_response = self.client.post(
            reverse('leaves:base_data_table', kwargs={'table_key': 'public_holidays'}),
            {
                'action': 'add',
                'name': 'Δοκιμαστική Αργία',
                'date': '2026-12-25',
                'year': '2026',
                'is_movable': 'False',
                'is_active': 'True',
            },
        )
        self.assertEqual(add_response.status_code, 302)
        holiday = PublicHoliday.objects.get(name='Δοκιμαστική Αργία')
        self.assertEqual(holiday.created_by_id, self.handler.pk)
