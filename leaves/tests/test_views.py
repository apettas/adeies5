"""
Unit tests for leave views
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.contrib.messages import get_messages
from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveRequest, LeaveType, LeaveBalance
from unittest.mock import patch

User = get_user_model()


class LeaveRequestViewTests(TestDataMixin, TestCase):
    """
    Tests για τα Leave Request views
    """
    
    def setUp(self):
        super().setUp()
        
        self.client = Client()
        
        # Δημιουργία LeaveType
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25
        )
        
        # Δημιουργία LeaveBalance
        self.leave_balance = LeaveBalance.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            total_days=25,
            used_days=0,
            remaining_days=25
        )
        
        # Δημιουργία LeaveRequest
        self.leave_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            start_date="2025-01-15",
            end_date="2025-01-20",
            total_days=5,
            description="Κανονική άδεια",
            status="SUBMITTED"
        )
        
    def test_leave_request_list_view_employee_access(self):
        """
        Test: Employee access στο leave request list
        """
        self.client.force_login(self.employee)
        
        response = self.client.get(reverse('leaves:leave_request_list'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.leave_request.description)
        self.assertContains(response, "Κανονική άδεια")
        
    def test_leave_request_list_view_manager_access(self):
        """
        Test: Manager access στο leave request list (sees subordinates)
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.get(reverse('leaves:leave_request_list'))
        
        self.assertEqual(response.status_code, 200)
        # Manager βλέπει τα requests των subordinates
        self.assertContains(response, self.leave_request.description)
        
    def test_leave_request_list_view_unauthenticated(self):
        """
        Test: Unauthenticated access redirects to login
        """
        response = self.client.get(reverse('leaves:leave_request_list'))
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        
    def test_leave_request_detail_view_owner_access(self):
        """
        Test: Owner access στο leave request detail
        """
        self.client.force_login(self.employee)
        
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.leave_request.description)
        self.assertContains(response, "Κανονική άδεια")
        
    def test_leave_request_detail_view_manager_access(self):
        """
        Test: Manager access στο subordinate leave request detail
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.leave_request.description)
        # Manager βλέπει approval buttons
        self.assertContains(response, "Έγκριση")
        self.assertContains(response, "Απόρριψη")
        
    def test_leave_request_detail_view_unauthorized_access(self):
        """
        Test: Unauthorized access στο leave request detail
        """
        self.client.force_login(self.kizilou)  # Wrong manager level
        
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.leave_request.pk})
        )
        
        # Μπορεί να δει το request αλλά όχι approval buttons
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Έγκριση")
        
    def test_leave_request_create_view_get(self):
        """
        Test: GET request στο leave request create view
        """
        self.client.force_login(self.employee)
        
        response = self.client.get(reverse('leaves:leave_request_create'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Νέα Αίτηση Άδειας")
        self.assertContains(response, "Κανονική Άδεια")
        
    def test_leave_request_create_view_post_valid(self):
        """
        Test: POST request στο leave request create view με valid data
        """
        self.client.force_login(self.employee)
        
        data = {
            'leave_type': self.leave_type.id,
            'start_date': '2025-02-15',
            'end_date': '2025-02-20',
            'total_days': 5,
            'description': 'Νέα αίτηση άδειας'
        }
        
        response = self.client.post(reverse('leaves:leave_request_create'), data)
        
        # Redirect μετά από successful creation
        self.assertEqual(response.status_code, 302)
        
        # Έλεγχος ότι δημιουργήθηκε το request
        new_request = LeaveRequest.objects.filter(
            user=self.employee,
            description='Νέα αίτηση άδειας'
        ).first()
        
        self.assertIsNotNone(new_request)
        self.assertEqual(new_request.status, 'SUBMITTED')
        
    def test_leave_request_create_view_post_invalid(self):
        """
        Test: POST request στο leave request create view με invalid data
        """
        self.client.force_login(self.employee)
        
        data = {
            'leave_type': self.leave_type.id,
            'start_date': '2025-02-20',  # End date πριν από start date
            'end_date': '2025-02-15',
            'total_days': 5,
            'description': ''  # Empty description
        }
        
        response = self.client.post(reverse('leaves:leave_request_create'), data)
        
        # Stays on form with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "form-error")
        
    def test_leave_request_approve_view_by_correct_manager(self):
        """
        Test: Approval από σωστό manager
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:leave_request_approve', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Έλεγχος ότι έγινε approve
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'APPROVED_MANAGER')
        self.assertEqual(self.leave_request.approved_by, self.dept_manager)
        
        # Έλεγχος success message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("εγκρίθηκε" in str(m) for m in messages))
        
    def test_leave_request_approve_view_by_wrong_manager(self):
        """
        Test: Approval από λάθος manager
        """
        self.client.force_login(self.kizilou)  # Wrong level
        
        response = self.client.post(
            reverse('leaves:leave_request_approve', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 403)  # Forbidden
        
        # Έλεγχος ότι ΔΕΝ έγινε approve
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'SUBMITTED')
        
    def test_leave_request_reject_view_by_correct_manager(self):
        """
        Test: Rejection από σωστό manager
        """
        self.client.force_login(self.dept_manager)
        
        data = {
            'rejection_reason': 'Απόρριψη για τεστ'
        }
        
        response = self.client.post(
            reverse('leaves:leave_request_reject', kwargs={'pk': self.leave_request.pk}),
            data
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Έλεγχος ότι έγινε reject
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'REJECTED')
        self.assertEqual(self.leave_request.rejected_by, self.dept_manager)
        self.assertEqual(self.leave_request.rejection_reason, 'Απόρριψη για τεστ')
        
    def test_leave_request_reject_view_without_reason(self):
        """
        Test: Rejection χωρίς λόγο
        """
        self.client.force_login(self.dept_manager)
        
        data = {
            'rejection_reason': ''  # Empty reason
        }
        
        response = self.client.post(
            reverse('leaves:leave_request_reject', kwargs={'pk': self.leave_request.pk}),
            data
        )
        
        # Stays on form with error
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Λόγος απόρριψης είναι απαραίτητος")
        
    def test_leave_request_cancel_view_by_owner(self):
        """
        Test: Cancellation από owner
        """
        self.client.force_login(self.employee)
        
        response = self.client.post(
            reverse('leaves:leave_request_cancel', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Έλεγχος ότι έγινε cancel
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'CANCELLED')
        
    def test_leave_request_cancel_view_by_non_owner(self):
        """
        Test: Cancellation από μη owner
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:leave_request_cancel', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 403)  # Forbidden
        
        # Έλεγχος ότι ΔΕΝ έγινε cancel
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'SUBMITTED')
        
    def test_leave_request_process_view_by_leave_handler(self):
        """
        Test: Processing από leave handler
        """
        # Πρώτα approval από manager
        self.leave_request.approve_request(self.dept_manager)
        
        self.client.force_login(self.leave_handler)
        
        response = self.client.post(
            reverse('leaves:leave_request_process', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Έλεγχος ότι έγινε process
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'APPROVED_FINAL')
        self.assertEqual(self.leave_request.processed_by, self.leave_handler)
        
    def test_leave_request_process_view_by_non_leave_handler(self):
        """
        Test: Processing από μη leave handler
        """
        # Πρώτα approval από manager
        self.leave_request.approve_request(self.dept_manager)
        
        self.client.force_login(self.employee)
        
        response = self.client.post(
            reverse('leaves:leave_request_process', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 403)  # Forbidden
        
        # Έλεγχος ότι ΔΕΝ έγινε process
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'APPROVED_MANAGER')


class LeaveRequestDashboardTests(TestDataMixin, TestCase):
    """
    Tests για το Leave Request Dashboard
    """
    
    def setUp(self):
        super().setUp()
        
        self.client = Client()
        
        # Δημιουργία LeaveType
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25
        )
        
        # Δημιουργία multiple requests
        self.employee_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            start_date="2025-01-15",
            end_date="2025-01-20",
            total_days=5,
            description="Employee request",
            status="SUBMITTED"
        )
        
        self.dept_manager_request = LeaveRequest.objects.create(
            user=self.dept_manager,
            leave_type=self.leave_type,
            start_date="2025-02-15",
            end_date="2025-02-20",
            total_days=5,
            description="Department manager request",
            status="SUBMITTED"
        )
        
        self.kizilou_request = LeaveRequest.objects.create(
            user=self.kizilou,
            leave_type=self.leave_type,
            start_date="2025-03-15",
            end_date="2025-03-20",
            total_days=5,
            description="Kizilou request",
            status="SUBMITTED"
        )
        
    def test_dashboard_employee_sees_own_requests_only(self):
        """
        Test: Employee βλέπει μόνο τα δικά του requests
        """
        self.client.force_login(self.employee)
        
        response = self.client.get(reverse('leaves:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee request")
        self.assertNotContains(response, "Department manager request")
        self.assertNotContains(response, "Kizilou request")
        
    def test_dashboard_department_manager_sees_subordinate_requests(self):
        """
        Test: Department manager βλέπει subordinate requests
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.get(reverse('leaves:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee request")  # Subordinate
        self.assertContains(response, "Department manager request")  # Own
        self.assertNotContains(response, "Kizilou request")  # Not subordinate
        
    def test_dashboard_kizilou_sees_autotelous_dn_requests(self):
        """
        Test: kizilou βλέπει AUTOTELOUS_DN requests
        """
        self.client.force_login(self.kizilou)
        
        response = self.client.get(reverse('leaves:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee request")  # AUTOTELOUS_DN
        self.assertContains(response, "Department manager request")  # AUTOTELOUS_DN
        self.assertContains(response, "Kizilou request")  # Own
        
    def test_dashboard_delegkos_sees_all_requests(self):
        """
        Test: delegkos βλέπει όλα τα requests
        """
        self.client.force_login(self.delegkos)
        
        response = self.client.get(reverse('leaves:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee request")
        self.assertContains(response, "Department manager request")
        self.assertContains(response, "Kizilou request")
        
    def test_dashboard_leave_handler_sees_approved_requests(self):
        """
        Test: Leave handler βλέπει approved requests
        """
        # Έγκριση requests
        self.employee_request.approve_request(self.dept_manager)
        self.dept_manager_request.approve_request(self.kizilou)
        
        self.client.force_login(self.leave_handler)
        
        response = self.client.get(reverse('leaves:dashboard'))
        
        self.assertEqual(response.status_code, 200)
        # Leave handler βλέπει approved requests για processing
        self.assertContains(response, "Employee request")
        self.assertContains(response, "Department manager request")
        
    def test_dashboard_filter_by_status(self):
        """
        Test: Dashboard filtering by status
        """
        # Έγκριση ενός request
        self.employee_request.approve_request(self.dept_manager)
        
        self.client.force_login(self.dept_manager)
        
        # Filter by SUBMITTED
        response = self.client.get(reverse('leaves:dashboard'), {'status': 'SUBMITTED'})
        self.assertContains(response, "Department manager request")
        self.assertNotContains(response, "Employee request")
        
        # Filter by APPROVED_MANAGER
        response = self.client.get(reverse('leaves:dashboard'), {'status': 'APPROVED_MANAGER'})
        self.assertContains(response, "Employee request")
        self.assertNotContains(response, "Department manager request")
        
    def test_dashboard_filter_by_user(self):
        """
        Test: Dashboard filtering by user
        """
        self.client.force_login(self.dept_manager)
        
        # Filter by employee
        response = self.client.get(reverse('leaves:dashboard'), {'user': self.employee.id})
        self.assertContains(response, "Employee request")
        self.assertNotContains(response, "Department manager request")
        
    def test_dashboard_filter_by_date_range(self):
        """
        Test: Dashboard filtering by date range
        """
        self.client.force_login(self.dept_manager)
        
        # Filter by January 2025
        response = self.client.get(reverse('leaves:dashboard'), {
            'start_date': '2025-01-01',
            'end_date': '2025-01-31'
        })
        self.assertContains(response, "Employee request")
        self.assertNotContains(response, "Department manager request")


class LeaveRequestPermissionTests(TestDataMixin, TestCase):
    """
    Tests για permissions στα leave request views
    """
    
    def setUp(self):
        super().setUp()
        
        self.client = Client()
        
        # Δημιουργία LeaveType
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25
        )
        
        # Δημιουργία different department user
        self.pdede_employee = User.objects.create_user(
            username="pdede_employee",
            email="pdede@test.com",
            first_name="PDEDE",
            last_name="Employee",
            department=self.pdede,
            role="EMPLOYEE"
        )
        
        self.pdede_request = LeaveRequest.objects.create(
            user=self.pdede_employee,
            leave_type=self.leave_type,
            start_date="2025-01-15",
            end_date="2025-01-20",
            total_days=5,
            description="PDEDE request",
            status="SUBMITTED"
        )
        
        self.autotelous_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            start_date="2025-02-15",
            end_date="2025-02-20",
            total_days=5,
            description="AUTOTELOUS_DN request",
            status="SUBMITTED"
        )
        
    def test_cross_department_access_denied(self):
        """
        Test: Cross-department access denied
        """
        self.client.force_login(self.employee)  # AUTOTELOUS_DN
        
        # Προσπάθεια access σε PDEDE request
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.pdede_request.pk})
        )
        
        self.assertEqual(response.status_code, 403)  # Forbidden
        
    def test_manager_cross_department_limited_access(self):
        """
        Test: Manager cross-department access
        """
        self.client.force_login(self.dept_manager)  # AUTOTELOUS_DN manager
        
        # Προσπάθεια access σε PDEDE request
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.pdede_request.pk})
        )
        
        # Μπορεί να δει αλλά όχι να εγκρίνει
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Έγκριση")
        
    def test_top_level_manager_access_all_departments(self):
        """
        Test: Top level manager access σε όλα τα departments
        """
        self.client.force_login(self.delegkos)  # PDEDE manager
        
        # Access σε AUTOTELOUS_DN request
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.autotelous_request.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "AUTOTELOUS_DN request")
        
        # Access σε PDEDE request
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.pdede_request.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PDEDE request")
        
    def test_leave_handler_access_all_approved_requests(self):
        """
        Test: Leave handler access σε όλα τα approved requests
        """
        # Έγκριση requests
        self.autotelous_request.approve_request(self.dept_manager)
        self.pdede_request.approve_request(self.delegkos)
        
        self.client.force_login(self.leave_handler)
        
        # Access σε AUTOTELOUS_DN approved request
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.autotelous_request.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Επεξεργασία")
        
        # Access σε PDEDE approved request
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.pdede_request.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Επεξεργασία")
        
    def test_approval_hierarchy_permissions(self):
        """
        Test: Approval hierarchy permissions
        """
        # Employee request μπορεί να εγκριθεί μόνο από dept_manager
        self.client.force_login(self.kizilou)
        
        response = self.client.post(
            reverse('leaves:leave_request_approve', kwargs={'pk': self.autotelous_request.pk})
        )
        
        self.assertEqual(response.status_code, 403)  # Forbidden
        
        # Department manager μπορεί να εγκρίνει
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:leave_request_approve', kwargs={'pk': self.autotelous_request.pk})
        )
        
        self.assertEqual(response.status_code, 302)  # Success redirect
        
    def test_rejection_hierarchy_permissions(self):
        """
        Test: Rejection hierarchy permissions
        """
        # Employee request μπορεί να απορριφθεί μόνο από dept_manager
        self.client.force_login(self.kizilou)
        
        response = self.client.post(
            reverse('leaves:leave_request_reject', kwargs={'pk': self.autotelous_request.pk}),
            {'rejection_reason': 'Test rejection'}
        )
        
        self.assertEqual(response.status_code, 403)  # Forbidden
        
        # Department manager μπορεί να απορρίψει
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:leave_request_reject', kwargs={'pk': self.autotelous_request.pk}),
            {'rejection_reason': 'Test rejection'}
        )
        
        self.assertEqual(response.status_code, 302)  # Success redirect


class LeaveRequestAjaxTests(TestDataMixin, TestCase):
    """
    Tests για Ajax functionality
    """
    
    def setUp(self):
        super().setUp()
        
        self.client = Client()
        
        # Δημιουργία LeaveType
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25
        )
        
        self.leave_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            start_date="2025-01-15",
            end_date="2025-01-20",
            total_days=5,
            description="Ajax test request",
            status="SUBMITTED"
        )
        
    def test_ajax_approve_request(self):
        """
        Test: Ajax approval request
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:leave_request_approve', kwargs={'pk': self.leave_request.pk}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Έλεγχος JSON response
        import json
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('message', data)
        
    def test_ajax_reject_request(self):
        """
        Test: Ajax rejection request
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:leave_request_reject', kwargs={'pk': self.leave_request.pk}),
            {'rejection_reason': 'Ajax rejection test'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Έλεγχος JSON response
        import json
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        self.assertIn('message', data)
        
    def test_ajax_get_subordinates(self):
        """
        Test: Ajax get subordinates
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.get(
            reverse('leaves:get_subordinates'),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Έλεγχος JSON response
        import json
        data = json.loads(response.content)
        self.assertIn('subordinates', data)
        
        # Έλεγχος ότι employee είναι subordinate
        subordinate_ids = [sub['id'] for sub in data['subordinates']]
        self.assertIn(self.employee.id, subordinate_ids)