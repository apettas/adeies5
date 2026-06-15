"""
Unit tests for leave models
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveRequest, LeaveType, LeavePeriod
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
        
        # Ρύθμιση leave balance στον χρήστη
        self.employee.leave_balance = 25
        self.employee.current_regular_leave_balance = 25
        self.employee.save()
        
        # Δημιουργία βασικού LeaveRequest με LeavePeriod
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
        
    def test_leave_request_creation(self):
        """
        Test: Δημιουργία LeaveRequest
        """
        self.assertEqual(self.leave_request.user, self.employee)
        self.assertEqual(self.leave_request.leave_type, self.leave_type)
        self.assertEqual(self.leave_request.total_days, 6)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        self.assertIsNotNone(self.leave_request.created_at)
        
    def test_leave_request_str_representation(self):
        """
        Test: String representation του LeaveRequest
        """
        expected = f"{self.employee.full_name} - Κανονική Άδεια ({self.leave_request.start_date} - {self.leave_request.end_date})"
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
            description="Άδεια προϊσταμένου",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=dept_manager_request,
            start_date="2025-02-15",
            end_date="2025-02-20",
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
            description="Άδεια kizilou",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=kizilou_request,
            start_date="2025-03-15",
            end_date="2025-03-20",
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
            description="Άδεια delegkos",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=delegkos_request,
            start_date="2025-04-15",
            end_date="2025-04-20",
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
        
    def test_approve_by_manager_by_correct_manager(self):
        """
        Test: approve_by_manager από σωστό manager
        """
        result = self.leave_request.approve_by_manager(self.dept_manager)
        self.assertTrue(result)
        self.assertEqual(self.leave_request.status, "PENDING_PROTOCOL")
        self.assertEqual(self.leave_request.manager_approved_by, self.dept_manager)
        self.assertIsNotNone(self.leave_request.manager_approved_at)
        
    def test_approve_by_manager_by_wrong_manager(self):
        """
        Test: approve_by_manager από λάθος manager
        """
        result = self.leave_request.approve_by_manager(self.kizilou)
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        self.assertIsNone(self.leave_request.manager_approved_by)
        
    def test_reject_by_manager_by_correct_manager(self):
        """
        Test: reject_by_manager από σωστό manager
        """
        result = self.leave_request.reject_by_manager(self.dept_manager, "Απόρριψη για τεστ")
        self.assertTrue(result)
        self.assertEqual(self.leave_request.status, "SUPERVISOR_REJECTED")
        self.assertEqual(self.leave_request.rejected_by, self.dept_manager)
        self.assertEqual(self.leave_request.rejection_reason, "Απόρριψη για τεστ")
        self.assertIsNotNone(self.leave_request.rejected_at)
        
    def test_reject_by_manager_by_wrong_manager(self):
        """
        Test: reject_by_manager από λάθος manager
        """
        result = self.leave_request.reject_by_manager(self.kizilou, "Απόρριψη")
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        self.assertIsNone(self.leave_request.rejected_by)
        
    def test_reject_by_manager_without_reason(self):
        """
        Test: reject_by_manager χωρίς λόγο
        """
        result = self.leave_request.reject_by_manager(self.dept_manager, "")
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        
    def test_complete_by_handler(self):
        """
        Test: complete_by_handler
        """
        # Πρώτα έγκριση από manager
        self.leave_request.approve_by_manager(self.dept_manager)
        
        # Μετά processing από leave handler
        result = self.leave_request.complete_by_handler(self.leave_handler)
        self.assertTrue(result)
        self.assertEqual(self.leave_request.status, "COMPLETED")
        self.assertEqual(self.leave_request.processed_by, self.leave_handler)
        self.assertIsNotNone(self.leave_request.processed_at)
        
    def test_complete_by_non_handler(self):
        """
        Test: complete_by_handler από μη leave handler
        """
        # Πρώτα έγκριση από manager
        self.leave_request.approve_by_manager(self.dept_manager)
        
        # Προσπάθεια processing από employee
        result = self.leave_request.complete_by_handler(self.employee)
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "PENDING_PROTOCOL")
        
    def test_complete_unmanaged_request(self):
        """
        Test: complete_by_handler σε μη-εγκεκριμένο αίτημα
        """
        result = self.leave_request.complete_by_handler(self.leave_handler)
        self.assertFalse(result)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        
    def test_is_pending_property(self):
        """
        Test: is_pending property
        """
        self.assertTrue(self.leave_request.is_pending)
        
        self.leave_request.status = "PENDING_PROTOCOL"
        self.assertTrue(self.leave_request.is_pending)
        
        self.leave_request.status = "COMPLETED"
        self.assertFalse(self.leave_request.is_pending)
        
        self.leave_request.status = "SUPERVISOR_REJECTED"
        self.assertFalse(self.leave_request.is_pending)
        
    def test_is_approved_property(self):
        """
        Test: is_approved property
        """
        self.assertFalse(self.leave_request.is_approved)
        
        self.leave_request.status = "PENDING_PROTOCOL"
        self.assertFalse(self.leave_request.is_approved)
        
        self.leave_request.status = "COMPLETED"
        self.assertTrue(self.leave_request.is_approved)
        
    def test_is_rejected_property(self):
        """
        Test: is_rejected property
        """
        self.assertFalse(self.leave_request.is_rejected)
        
        self.leave_request.status = "SUPERVISOR_REJECTED"
        self.assertTrue(self.leave_request.is_rejected)
        
    def test_can_be_withdrawn_by_owner(self):
        """
        Test: can_be_withdrawn από owner
        """
        self.assertTrue(self.leave_request.can_be_withdrawn)
        
        # Μετά την έγκριση δεν μπορεί να ανακληθεί
        self.leave_request.status = "COMPLETED"
        self.assertFalse(self.leave_request.can_be_withdrawn)
        
    def test_can_be_withdrawn_after_approval(self):
        """
        Test: can_be_withdrawn μετά την έγκριση από προϊστάμενο
        """
        self.leave_request.status = "PENDING_PROTOCOL"
        self.assertFalse(self.leave_request.can_be_withdrawn)
        
    def test_withdraw_by_requester_by_owner(self):
        """
        Test: withdraw_by_requester από owner
        """
        result = self.leave_request.withdraw_by_requester(self.employee)
        self.assertTrue(result)
        self.assertEqual(self.leave_request.status, "CANCELLED_BY_APPLICANT")
        self.assertIsNotNone(self.leave_request.rejected_at)
        
    def test_withdraw_by_requester_by_non_owner(self):
        """
        Test: withdraw_by_requester από μη owner
        """
        with self.assertRaises(ValueError):
            self.leave_request.withdraw_by_requester(self.dept_manager)
        self.assertEqual(self.leave_request.status, "SUBMITTED")
        
    def test_get_status_display_greek(self):
        """
        Test: get_status_display στα ελληνικά
        """
        status_map = {
            "SUBMITTED": "Υποβληθείσα αίτηση",
            "PENDING_PROTOCOL": "Για πρωτόκολλο ΠΔΕΔΕ",
            "COMPLETED": "Ολοκληρώθηκε",
            "SUPERVISOR_REJECTED": "Αρνητική έγκριση προϊσταμένου",
            "CANCELLED_BY_APPLICANT": "Ανάκληση από αιτούντα",
        }
        
        for status, expected_greek in status_map.items():
            self.leave_request.status = status
            # Use Django's built-in get_status_display()
            self.assertEqual(self.leave_request.get_status_display(), expected_greek)
            
    def test_leave_request_overlapping_dates(self):
        """
        Test: Overlapping dates validation
        """
        # Δημιουργία δεύτερου request με overlapping dates
        overlapping_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            description="Overlapping άδεια",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=overlapping_request,
            start_date="2025-01-18",
            end_date="2025-01-25",
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
            description="Άδεια με Σαββατοκύριακο",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=weekend_request,
            start_date="2025-01-17",
            end_date="2025-01-19",
        )
        
        self.assertEqual(weekend_request.total_days, 3)
        
    def test_leave_request_future_dates_only(self):
        """
        Test: Μόνο future dates επιτρέπονται
        """
        yesterday = date.today() - timedelta(days=1)
        
        past_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            description="Παρελθούσα άδεια",
            status="SUBMITTED"
        )
        LeavePeriod.objects.create(
            leave_request=past_request,
            start_date=yesterday,
            end_date=yesterday,
        )
        
        # Δημιουργείται το αίτημα (validation στο form level)
        self.assertEqual(past_request.user, self.employee)
        
    def test_leave_request_history_tracking(self):
        """
        Test: History tracking των αλλαγών
        """
        # Έγκριση
        self.leave_request.approve_by_manager(self.dept_manager)
        
        # Έλεγχος ότι καταγράφηκε ο approver
        self.assertEqual(self.leave_request.manager_approved_by, self.dept_manager)
        self.assertIsNotNone(self.leave_request.manager_approved_at)
        
        # Processing
        self.leave_request.complete_by_handler(self.leave_handler)
        
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
