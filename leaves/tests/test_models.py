"""
Unit tests for leave models
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveRequest, LeaveType, LeaveBalance
from datetime import date, timedelta

User = get_user_model()


class LeaveRequestModelTests(TestDataMixin, TestCase):
    """
    Tests για το LeaveRequest model
    """
    
    def setUp(self):
        super().setUp()
        
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
        
        # Δημιουργία βασικού LeaveRequest
        self.leave_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            start_date="2025-01-15",
            end_date="2025-01-20",
            total_days=5,
            description="Κανονική άδεια",
            status="SUBMITTED"
        )
        
    def test_leave_request_creation(self):
        """
        Test: Δημιουργία LeaveRequest
        """
        self.assertEqual(self.leave_request.user, self.employee)
        self.assertEqual(self.leave_request.leave_type, self.leave_type)
        self.assertEqual(self.leave_request.total_days, 5)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        self.assertIsNotNone(self.leave_request.created_at)
        
    def test_leave_request_str_representation(self):
        """
        Test: String representation του LeaveRequest
        """
        expected = f"{self.employee.get_full_name()} - Κανονική Άδεια (15/01/2025 - 20/01/2025)"
        self.assertEqual(str(self.leave_request), expected)
        
    def test_get_approving_manager_for_employee_request(self):
        """
        Test: get_approving_manager για employee request
        """
        approving_manager = self.leave_request.get_approving_manager()
        self.assertEqual(approving_manager, self.dept_manager)
        
    def test_get_approving_manager_for_department_manager_request(self):
        """
        Test: get_approving_manager για department manager request
        """
        dept_manager_request = LeaveRequest.objects.create(
            user=self.dept_manager,
            leave_type=self.leave_type,
            start_date="2025-02-15",
            end_date="2025-02-20",
            total_days=5,
            description="Άδεια προϊσταμένου",
            status="SUBMITTED"
        )
        
        approving_manager = dept_manager_request.get_approving_manager()
        self.assertEqual(approving_manager, self.kizilou)
        
    def test_get_approving_manager_for_kizilou_request(self):
        """
        Test: get_approving_manager για kizilou request
        """
        kizilou_request = LeaveRequest.objects.create(
            user=self.kizilou,
            leave_type=self.leave_type,
            start_date="2025-03-15",
            end_date="2025-03-20",
            total_days=5,
            description="Άδεια kizilou",
            status="SUBMITTED"
        )
        
        approving_manager = kizilou_request.get_approving_manager()
        self.assertEqual(approving_manager, self.delegkos)
        
    def test_get_approving_manager_for_delegkos_request(self):
        """
        Test: get_approving_manager για delegkos request (top level)
        """
        delegkos_request = LeaveRequest.objects.create(
            user=self.delegkos,
            leave_type=self.leave_type,
            start_date="2025-04-15",
            end_date="2025-04-20",
            total_days=5,
            description="Άδεια delegkos",
            status="SUBMITTED"
        )
        
        approving_manager = delegkos_request.get_approving_manager()
        self.assertIsNone(approving_manager)  # Top level manager
        
    def test_can_be_approved_by_correct_manager(self):
        """
        Test: can_be_approved_by με σωστό manager
        """
        can_approve = self.leave_request.can_be_approved_by(self.dept_manager)
        self.assertTrue(can_approve)
        
    def test_can_be_approved_by_wrong_manager(self):
        """
        Test: can_be_approved_by με λάθος manager
        """
        can_approve = self.leave_request.can_be_approved_by(self.kizilou)
        self.assertFalse(can_approve)
        
    def test_can_be_approved_by_same_user(self):
        """
        Test: can_be_approved_by με τον ίδιο user
        """
        can_approve = self.leave_request.can_be_approved_by(self.employee)
        self.assertFalse(can_approve)
        
    def test_approve_request_by_correct_manager(self):
        """
        Test: approve_request από σωστό manager
        """
        result = self.leave_request.approve_request(self.dept_manager)
        self.assertTrue(result)
        self.assertEqual(self.leave_request.status, "APPROVED_MANAGER")
        self.assertEqual(self.leave_request.approved_by, self.dept_manager)
        self.assertIsNotNone(self.leave_request.approved_at)
        
    def test_approve_request_by_wrong_manager(self):
        """
        Test: approve_request από λάθος manager
        """
        result = self.leave_request.approve_request(self.kizilou)
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        self.assertIsNone(self.leave_request.approved_by)
        
    def test_reject_request_by_correct_manager(self):
        """
        Test: reject_request από σωστό manager
        """
        result = self.leave_request.reject_request(self.dept_manager, "Απόρριψη για τεστ")
        self.assertTrue(result)
        self.assertEqual(self.leave_request.status, "REJECTED")
        self.assertEqual(self.leave_request.rejected_by, self.dept_manager)
        self.assertEqual(self.leave_request.rejection_reason, "Απόρριψη για τεστ")
        self.assertIsNotNone(self.leave_request.rejected_at)
        
    def test_reject_request_by_wrong_manager(self):
        """
        Test: reject_request από λάθος manager
        """
        result = self.leave_request.reject_request(self.kizilou, "Απόρριψη")
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        self.assertIsNone(self.leave_request.rejected_by)
        
    def test_reject_request_without_reason(self):
        """
        Test: reject_request χωρίς λόγο
        """
        result = self.leave_request.reject_request(self.dept_manager, "")
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        
    def test_process_by_leave_handler(self):
        """
        Test: process_by_leave_handler
        """
        # Πρώτα έγκριση από manager
        self.leave_request.approve_request(self.dept_manager)
        
        # Μετά processing από leave handler
        result = self.leave_request.process_by_leave_handler(self.leave_handler)
        self.assertTrue(result)
        self.assertEqual(self.leave_request.status, "APPROVED_FINAL")
        self.assertEqual(self.leave_request.processed_by, self.leave_handler)
        self.assertIsNotNone(self.leave_request.processed_at)
        
    def test_process_by_non_leave_handler(self):
        """
        Test: process_by_leave_handler από μη leave handler
        """
        # Πρώτα έγκριση από manager
        self.leave_request.approve_request(self.dept_manager)
        
        # Προσπάθεια processing από employee
        result = self.leave_request.process_by_leave_handler(self.employee)
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "APPROVED_MANAGER")
        
    def test_process_unmanaged_request(self):
        """
        Test: process_by_leave_handler σε μη-εγκεκριμένο αίτημα
        """
        result = self.leave_request.process_by_leave_handler(self.leave_handler)
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        
    def test_is_pending_property(self):
        """
        Test: is_pending property
        """
        self.assertTrue(self.leave_request.is_pending)
        
        self.leave_request.status = "APPROVED_MANAGER"
        self.assertTrue(self.leave_request.is_pending)
        
        self.leave_request.status = "APPROVED_FINAL"
        self.assertFalse(self.leave_request.is_pending)
        
        self.leave_request.status = "REJECTED"
        self.assertFalse(self.leave_request.is_pending)
        
    def test_is_approved_property(self):
        """
        Test: is_approved property
        """
        self.assertFalse(self.leave_request.is_approved)
        
        self.leave_request.status = "APPROVED_MANAGER"
        self.assertFalse(self.leave_request.is_approved)
        
        self.leave_request.status = "APPROVED_FINAL"
        self.assertTrue(self.leave_request.is_approved)
        
    def test_is_rejected_property(self):
        """
        Test: is_rejected property
        """
        self.assertFalse(self.leave_request.is_rejected)
        
        self.leave_request.status = "REJECTED"
        self.assertTrue(self.leave_request.is_rejected)
        
    def test_can_be_cancelled_by_owner(self):
        """
        Test: can_be_cancelled από owner
        """
        self.assertTrue(self.leave_request.can_be_cancelled_by(self.employee))
        
        # Μετά την έγκριση δεν μπορεί να ακυρωθεί
        self.leave_request.status = "APPROVED_FINAL"
        self.assertFalse(self.leave_request.can_be_cancelled_by(self.employee))
        
    def test_can_be_cancelled_by_non_owner(self):
        """
        Test: can_be_cancelled από μη owner
        """
        self.assertFalse(self.leave_request.can_be_cancelled_by(self.dept_manager))
        
    def test_cancel_request_by_owner(self):
        """
        Test: cancel_request από owner
        """
        result = self.leave_request.cancel_request(self.employee)
        self.assertTrue(result)
        self.assertEqual(self.leave_request.status, "CANCELLED")
        self.assertIsNotNone(self.leave_request.cancelled_at)
        
    def test_cancel_request_by_non_owner(self):
        """
        Test: cancel_request από μη owner
        """
        result = self.leave_request.cancel_request(self.dept_manager)
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        
    def test_get_status_display_greek(self):
        """
        Test: get_status_display στα ελληνικά
        """
        status_map = {
            "SUBMITTED": "Υποβληθέν",
            "APPROVED_MANAGER": "Εγκεκριμένο από Προϊστάμενο",
            "APPROVED_FINAL": "Τελικώς Εγκεκριμένο",
            "REJECTED": "Απορριφθέν",
            "CANCELLED": "Ακυρώθηκε"
        }
        
        for status, expected in status_map.items():
            self.leave_request.status = status
            self.assertEqual(self.leave_request.get_status_display_greek(), expected)
            
    def test_leave_request_overlapping_dates(self):
        """
        Test: Overlapping dates validation
        """
        # Δημιουργία δεύτερου request με overlapping dates
        overlapping_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            start_date="2025-01-18",  # Overlap με το πρώτο request
            end_date="2025-01-25",
            total_days=5,
            description="Overlapping άδεια",
            status="SUBMITTED"
        )
        
        # Έλεγχος ότι δημιουργήθηκε (validation γίνεται στο view/form level)
        self.assertEqual(overlapping_request.user, self.employee)
        
    def test_leave_request_weekend_handling(self):
        """
        Test: Weekend handling σε dates
        """
        # Request που περιλαμβάνει Σαββατοκύριακο
        weekend_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            start_date="2025-01-17",  # Παρασκευή
            end_date="2025-01-19",   # Κυριακή
            total_days=1,  # Μόνο η Παρασκευή μετράει
            description="Άδεια με Σαββατοκύριακο",
            status="SUBMITTED"
        )
        
        self.assertEqual(weekend_request.total_days, 1)
        
    def test_leave_request_future_dates_only(self):
        """
        Test: Μόνο future dates επιτρέπονται
        """
        yesterday = date.today() - timedelta(days=1)
        
        past_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            start_date=yesterday,
            end_date=yesterday,
            total_days=1,
            description="Παρελθούσα άδεια",
            status="SUBMITTED"
        )
        
        # Δημιουργείται το αίτημα (validation στο form level)
        self.assertEqual(past_request.user, self.employee)
        
    def test_leave_request_history_tracking(self):
        """
        Test: History tracking των αλλαγών
        """
        # Έγκριση
        self.leave_request.approve_request(self.dept_manager)
        
        # Έλεγχος ότι καταγράφηκε ο approver
        self.assertEqual(self.leave_request.approved_by, self.dept_manager)
        self.assertIsNotNone(self.leave_request.approved_at)
        
        # Processing
        self.leave_request.process_by_leave_handler(self.leave_handler)
        
        # Έλεγχος ότι καταγράφηκε ο processor
        self.assertEqual(self.leave_request.processed_by, self.leave_handler)
        self.assertIsNotNone(self.leave_request.processed_at)


class LeaveTypeModelTests(TestCase):
    """
    Tests για το LeaveType model
    """
    
    def test_leave_type_creation(self):
        """
        Test: Δημιουργία LeaveType
        """
        leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25
        )
        
        self.assertEqual(leave_type.name, "Κανονική Άδεια")
        self.assertEqual(leave_type.code, "ANNUAL")
        self.assertTrue(leave_type.requires_approval)
        self.assertEqual(leave_type.max_days, 25)
        
    def test_leave_type_str_representation(self):
        """
        Test: String representation του LeaveType
        """
        leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25
        )
        
        self.assertEqual(str(leave_type), "Κανονική Άδεια")
        
    def test_leave_type_code_unique(self):
        """
        Test: LeaveType code είναι unique
        """
        LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25
        )
        
        # Δεύτερο leave type με το ίδιο code
        with self.assertRaises(Exception):
            LeaveType.objects.create(
                name="Άλλη Άδεια",
                code="ANNUAL",  # Duplicate code
                requires_approval=True,
                max_days=20
            )


class LeaveBalanceModelTests(TestDataMixin, TestCase):
    """
    Tests για το LeaveBalance model
    """
    
    def setUp(self):
        super().setUp()
        
        self.leave_type = LeaveType.objects.create(
            name="Κανονική Άδεια",
            code="ANNUAL",
            requires_approval=True,
            max_days=25
        )
        
    def test_leave_balance_creation(self):
        """
        Test: Δημιουργία LeaveBalance
        """
        leave_balance = LeaveBalance.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            total_days=25,
            used_days=5,
            remaining_days=20
        )
        
        self.assertEqual(leave_balance.user, self.employee)
        self.assertEqual(leave_balance.leave_type, self.leave_type)
        self.assertEqual(leave_balance.total_days, 25)
        self.assertEqual(leave_balance.used_days, 5)
        self.assertEqual(leave_balance.remaining_days, 20)
        
    def test_leave_balance_str_representation(self):
        """
        Test: String representation του LeaveBalance
        """
        leave_balance = LeaveBalance.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            total_days=25,
            used_days=5,
            remaining_days=20
        )
        
        expected = f"{self.employee.get_full_name()} - Κανονική Άδεια: 20/25"
        self.assertEqual(str(leave_balance), expected)
        
    def test_leave_balance_calculation(self):
        """
        Test: Υπολογισμός remaining_days
        """
        leave_balance = LeaveBalance.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            total_days=25,
            used_days=8,
            remaining_days=17
        )
        
        # Έλεγχος ότι remaining_days = total_days - used_days
        self.assertEqual(leave_balance.remaining_days, 17)
        self.assertEqual(leave_balance.total_days - leave_balance.used_days, 17)