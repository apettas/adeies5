"""Tests για role switcher, dashboard redirect και session routing."""
from django.test import TestCase, RequestFactory
from django.urls import reverse

from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveRequest, LeaveType
from leaves.role_context import (
    get_role_nav_items,
    get_role_pending_counts,
    resolve_default_dashboard_name,
)


class DashboardRoleContextTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.leave_type = LeaveType.objects.create(
            code='REGULAR',
            name='Κανονική Άδεια',
            is_active=True,
        )
        self.client.force_login(self.dept_manager)

    def test_manager_pending_count_includes_submitted_requests(self):
        LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            status='SUBMITTED',
        )
        counts = get_role_pending_counts(self.dept_manager)
        self.assertEqual(counts['manager'], 1)

    def test_resolve_default_dashboard_prefers_role_with_pending_work(self):
        LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            status='SUBMITTED',
        )
        self.dept_manager.roles.add(self.leave_handler_role)

        url_name = resolve_default_dashboard_name(self.dept_manager, {})
        self.assertEqual(url_name, 'leaves:manager_dashboard')

    def test_resolve_default_dashboard_uses_session_last_role(self):
        url_name = resolve_default_dashboard_name(
            self.leave_handler,
            {'active_dashboard_role': 'handler'},
        )
        self.assertEqual(url_name, 'leaves:handler_dashboard')

    def test_role_nav_items_marks_active_dashboard(self):
        factory = RequestFactory()
        request = factory.get(reverse('leaves:manager_dashboard'))
        request.user = self.dept_manager
        request.resolver_match = type('RM', (), {'url_name': 'manager_dashboard'})()

        items = get_role_nav_items(self.dept_manager, request)
        manager_item = next(i for i in items if i['key'] == 'manager')
        self.assertTrue(manager_item['is_active'])


class DashboardRedirectViewTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.leave_type = LeaveType.objects.create(
            code='REGULAR',
            name='Κανονική Άδεια',
            is_active=True,
        )

    def test_dashboard_redirect_goes_to_manager_when_pending_approvals(self):
        LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            status='SUBMITTED',
        )
        self.client.force_login(self.dept_manager)
        response = self.client.get(reverse('leaves:dashboard_redirect'))
        self.assertRedirects(response, reverse('leaves:manager_dashboard'))

    def test_employee_dashboard_sets_session_role(self):
        self.client.force_login(self.employee)
        session = self.client.session
        session.save()
        self.client.get(reverse('leaves:employee_dashboard'))
        self.assertEqual(self.client.session.get('active_dashboard_role'), 'employee')

    def test_handler_dashboard_defaults_to_protocol_tab(self):
        self.client.force_login(self.leave_handler)
        response = self.client.get(reverse('leaves:handler_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['active_tab'], 'protocol')

    def test_role_switcher_visible_for_multi_role_user(self):
        self.dept_manager.roles.add(self.leave_handler_role)
        self.client.force_login(self.dept_manager)
        response = self.client.get(reverse('leaves:manager_dashboard'))
        self.assertContains(response, 'Ρόλος:')
        self.assertContains(response, 'Προϊστάμενος')
        self.assertContains(response, 'Χειριστής Αδειών')
