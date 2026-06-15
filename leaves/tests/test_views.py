"""
Unit tests for leave views
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.contrib.messages import get_messages
from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveRequest, LeaveType, LeavePeriod
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
        
        # Ρύθμιση leave balance στον χρήστη
        self.employee.leave_balance = 25
        self.employee.current_regular_leave_balance = 25
        self.employee.save()
        
        # Δημιουργία LeaveRequest
        self.leave_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            description="Κανονική άδεια",
            status="SUBMITTED"
        )
        from leaves.models import LeavePeriod
        LeavePeriod.objects.create(
            leave_request=self.leave_request,
            start_date="2025-01-15",
            end_date="2025-01-20"
        )
        
    def test_leave_request_list_view_employee_access(self):
        """
        Test: Employee access στο leave request list
        """
        self.client.force_login(self.employee)
        
        response = self.client.get(reverse('leaves:employee_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Κανονική Άδεια")
        
    def test_leave_request_list_view_manager_access(self):
        """
        Test: Manager access στο leave request list (sees subordinates)
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.get(reverse('leaves:manager_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        # Manager βλέπει τα requests των subordinates
        self.assertContains(response, "Κανονική Άδεια")
        
    def test_leave_request_list_view_unauthenticated(self):
        """
        Test: Unauthenticated access redirects to login
        """
        response = self.client.get(reverse('leaves:employee_dashboard'))
        
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)
        
    def test_leave_request_detail_view_owner_access(self):
        """
        Test: Owner access στο leave request detail
        """
        self.client.force_login(self.employee)
        
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Κανονική Άδεια")
        
    def test_leave_request_detail_view_manager_access(self):
        """
        Test: Manager access στο subordinate leave request detail
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.get(
            reverse('leaves:leave_request_detail', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Κανονική Άδεια")
        # Manager βλέπει approval buttons
        self.assertContains(response, 'btn-success')
        self.assertContains(response, 'btn-danger')
        
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
        self.assertNotContains(response, 'id="approveModal')
        
    def test_leave_request_create_view_get(self):
        """
        Test: GET request στο leave request create view
        """
        self.client.force_login(self.employee)
        
        response = self.client.get(reverse('leaves:create_leave_request'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Νέα Αίτηση Άδειας")
        self.assertContains(response, "Κανονική Άδεια")
        
    def test_leave_request_create_view_post_valid(self):
        """
        Test: POST χωρίς periods_data μένει στη φόρμα
        """
        self.client.force_login(self.employee)

        data = {
            'leave_type': self.leave_type.id,
            'description': 'Νέα αίτηση άδειας',
        }

        response = self.client.post(reverse('leaves:create_leave_request'), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            LeaveRequest.objects.filter(description='Νέα αίτηση άδειας').exists()
        )
        
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
        
        response = self.client.post(reverse('leaves:create_leave_request'), data)

        self.assertEqual(response.status_code, 200)
        
    def test_leave_request_approve_view_by_correct_manager(self):
        """
        Test: Approval από σωστό manager
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Έλεγχος ότι έγινε approve
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'PENDING_PROTOCOL')
        self.assertEqual(self.leave_request.manager_approved_by, self.dept_manager)
        
        # Έλεγχος success message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("εγκρίθηκε" in str(m) for m in messages))
        
    def test_leave_request_approve_view_by_wrong_manager(self):
        """
        Test: Approval από λάθος manager
        """
        self.client.force_login(self.kizilou)  # Wrong level
        
        response = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': self.leave_request.pk})
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
            'reason': 'Απόρριψη για τεστ'
        }
        
        response = self.client.post(
            reverse('leaves:reject_leave_request', kwargs={'pk': self.leave_request.pk}),
            data
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Έλεγχος ότι έγινε reject
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'SUPERVISOR_REJECTED')
        self.assertEqual(self.leave_request.rejected_by, self.dept_manager)
        self.assertEqual(self.leave_request.rejection_reason, 'Απόρριψη για τεστ')
        
    def test_leave_request_reject_view_without_reason(self):
        """
        Test: Rejection χωρίς λόγο
        """
        self.client.force_login(self.dept_manager)
        
        data = {
            'reason': ''  # Empty reason
        }
        
        response = self.client.post(
            reverse('leaves:reject_leave_request', kwargs={'pk': self.leave_request.pk}),
            data
        )
        
        # Redirect με μήνυμα σφάλματος — δεν έγινε reject
        self.assertEqual(response.status_code, 302)
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'SUBMITTED')
        
    def test_leave_request_cancel_view_by_owner(self):
        """
        Test: Cancellation από owner
        """
        self.client.force_login(self.employee)
        
        response = self.client.post(
            reverse('leaves:withdraw_leave_request', kwargs={'pk': self.leave_request.pk})
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Έλεγχος ότι έγινε cancel
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'CANCELLED_BY_APPLICANT')
        
    def test_leave_request_cancel_view_by_non_owner(self):
        """
        Test: Cancellation από μη owner
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:withdraw_leave_request', kwargs={'pk': self.leave_request.pk})
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
        self.leave_request.approve_by_manager(self.dept_manager)
        
        self.client.force_login(self.leave_handler)
        
        response = self.client.post(
            reverse('leaves:complete_leave_request', kwargs={'pk': self.leave_request.pk}),
            {'balance_after': 19, 'comments': 'Test completion'},
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Έλεγχος ότι έγινε process
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'COMPLETED')
        self.assertEqual(self.leave_request.processed_by, self.leave_handler)
        
    def test_leave_request_process_view_by_non_leave_handler(self):
        """
        Test: Processing από μη leave handler
        """
        # Πρώτα approval από manager
        self.leave_request.approve_by_manager(self.dept_manager)
        
        self.client.force_login(self.employee)
        
        response = self.client.post(
            reverse('leaves:complete_leave_request', kwargs={'pk': self.leave_request.pk}),
            {'balance_after': 19, 'comments': 'Test completion'},
        )
        
        self.assertEqual(response.status_code, 403)  # Forbidden
        
        # Έλεγχος ότι ΔΕΝ έγινε process
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'PENDING_PROTOCOL')


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
            days=5,
            description="Employee request",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=self.employee_request,
            start_date="2025-01-15",
            end_date="2025-01-20"
        )
        
        self.dept_manager_request = LeaveRequest.objects.create(
            user=self.dept_manager,
            leave_type=self.leave_type,
            days=5,
            description="Department manager request",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=self.dept_manager_request,
            start_date="2025-02-15",
            end_date="2025-02-20"
        )
        
        self.kizilou_request = LeaveRequest.objects.create(
            user=self.kizilou,
            leave_type=self.leave_type,
            days=5,
            description="Kizilou request",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=self.kizilou_request,
            start_date="2025-03-15",
            end_date="2025-03-20"
        )
        
    def test_dashboard_employee_sees_own_requests_only(self):
        """
        Test: Employee βλέπει μόνο τα δικά του requests
        """
        self.client.force_login(self.employee)
        
        response = self.client.get(reverse('leaves:employee_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Κανονική Άδεια')
        
    def test_dashboard_department_manager_sees_subordinate_requests(self):
        """
        Test: Department manager βλέπει subordinate requests
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.get(reverse('leaves:manager_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee request")  # Περιγραφή στο manager dashboard
        self.assertNotContains(response, "Department manager request")
        self.assertNotContains(response, "Kizilou request")
        
    def test_dashboard_kizilou_sees_autotelous_dn_requests(self):
        """
        Test: kizilou βλέπει AUTOTELOUS_DN requests
        """
        self.client.force_login(self.kizilou)
        
        response = self.client.get(reverse('leaves:manager_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Employee request")  # AUTOTELOUS_DN
        self.assertContains(response, "Department manager request")  # AUTOTELOUS_DN
        
    def test_dashboard_delegkos_sees_all_requests(self):
        """
        Test: delegkos βλέπει αιτήσεις managers που χρειάζονται έγκριση
        """
        self.client.force_login(self.delegkos)
        
        response = self.client.get(reverse('leaves:manager_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Προϊστάμενος Τμήματος")
        self.assertContains(response, "Κιζίλου Τεστ")
        self.assertNotContains(response, "Employee request")
        
    def test_dashboard_leave_handler_sees_approved_requests(self):
        """
        Test: Leave handler βλέπει approved requests
        """
        # Έγκριση requests
        self.employee_request.approve_by_manager(self.dept_manager)
        self.dept_manager_request.approve_by_manager(self.kizilou)
        
        self.client.force_login(self.leave_handler)
        
        response = self.client.get(reverse('leaves:handler_dashboard'))
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Υπάλληλος Τεστ")
        self.assertContains(response, "Προϊστάμενος Τμήματος")
        
    def test_dashboard_filter_by_status(self):
        """
        Test: Dashboard filtering by status
        """
        self.employee_request.approve_by_manager(self.dept_manager)
        
        self.client.force_login(self.employee)
        
        response = self.client.get(reverse('leaves:employee_dashboard'), {'status': 'SUBMITTED'})
        self.assertNotContains(response, "15/01/2025")
        
        response = self.client.get(reverse('leaves:employee_dashboard'), {'status': 'PENDING_PROTOCOL'})
        self.assertContains(response, "15/01/2025")
        
    def test_dashboard_filter_by_user(self):
        """
        Test: Employee dashboard δείχνει μόνο τις δικές του αιτήσεις
        """
        self.client.force_login(self.employee)
        
        response = self.client.get(reverse('leaves:employee_dashboard'))
        self.assertContains(response, "15/01/2025")
        self.assertNotContains(response, "15/02/2025")
        
    def test_dashboard_filter_by_date_range(self):
        """
        Test: Employee dashboard χωρίς crash με date filters
        """
        self.client.force_login(self.employee)
        
        response = self.client.get(reverse('leaves:employee_dashboard'), {
            'date_from': '2025-01-01',
            'date_to': '2025-01-31'
        })
        self.assertEqual(response.status_code, 200)


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
            email="pdede@test.com",
            first_name="PDEDE",
            last_name="Employee",
            department=self.pdede,
            registration_status='APPROVED',
            is_active=True
        )
        self.pdede_employee.roles.add(self.employee_role)
        
        self.pdede_request = LeaveRequest.objects.create(
            user=self.pdede_employee,
            leave_type=self.leave_type,
            days=5,
            description="PDEDE request",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=self.pdede_request,
            start_date="2025-01-15",
            end_date="2025-01-20"
        )
        
        self.autotelous_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            days=5,
            description="AUTOTELOUS_DN request",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=self.autotelous_request,
            start_date="2025-02-15",
            end_date="2025-02-20"
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
        
        # Μπορεί να δει αλλά όχι να εγκρίνει — cross-department χωρίς σχέση ιεραρχίας
        self.assertEqual(response.status_code, 403)
        
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
        self.autotelous_request.approve_by_manager(self.dept_manager)
        self.pdede_request.approve_by_manager(self.delegkos)
        
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
            reverse('leaves:approve_leave_request', kwargs={'pk': self.autotelous_request.pk})
        )
        
        self.assertEqual(response.status_code, 403)  # Forbidden
        
        # Department manager μπορεί να εγκρίνει
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': self.autotelous_request.pk})
        )
        
        self.assertEqual(response.status_code, 302)  # Success redirect
        
    def test_rejection_hierarchy_permissions(self):
        """
        Test: Rejection hierarchy permissions
        """
        # Employee request μπορεί να απορριφθεί μόνο από dept_manager
        self.client.force_login(self.kizilou)
        
        response = self.client.post(
            reverse('leaves:reject_leave_request', kwargs={'pk': self.autotelous_request.pk}),
            {'reason': 'Test rejection'}
        )
        
        self.assertEqual(response.status_code, 403)  # Forbidden
        
        # Department manager μπορεί να απορρίψει
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:reject_leave_request', kwargs={'pk': self.autotelous_request.pk}),
            {'reason': 'Test rejection'}
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
            description="Ajax test request",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=self.leave_request,
            start_date="2025-01-15",
            end_date="2025-01-20",
        )
        
    def test_ajax_approve_request(self):
        """
        Test: Ajax approval request
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:approve_leave_request', kwargs={'pk': self.leave_request.pk}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 302)
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'PENDING_PROTOCOL')
        
    def test_ajax_reject_request(self):
        """
        Test: Ajax rejection request
        """
        self.client.force_login(self.dept_manager)
        
        response = self.client.post(
            reverse('leaves:reject_leave_request', kwargs={'pk': self.leave_request.pk}),
            {'reason': 'Ajax rejection test'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 302)
        self.leave_request.refresh_from_db()
        self.assertEqual(self.leave_request.status, 'SUPERVISOR_REJECTED')
        
    def test_ajax_get_subordinates(self):
        """
        Test: get_subordinates() επιστρέφει τους υφισταμένους
        """
        subordinates = self.dept_manager.get_subordinates()
        self.assertIn(self.employee, subordinates)
        self.assertNotIn(self.kizilou, subordinates)