"""
Unit tests for leave permission template tags
"""
from django.test import TestCase
from django.template import Context, Template
from django.contrib.auth import get_user_model
from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveRequest, LeaveType
from leaves.tests.helpers import create_submitted_leave_request
from leaves.templatetags.leave_permissions import can_manager_approve

User = get_user_model()


class LeavePermissionTemplateTagTests(TestDataMixin, TestCase):
    """
    Tests για τα template tags του leave permission system
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
        
        # Δημιουργία LeaveRequest από employee
        self.employee_leave_request = create_submitted_leave_request(
            self.employee, self.leave_type, "Κανονική άδεια", "2025-01-15", "2025-01-20"
        )
        
        self.dept_manager_leave_request = create_submitted_leave_request(
            self.dept_manager, self.leave_type, "Κανονική άδεια προϊσταμένου", "2025-02-15", "2025-02-20"
        )
        
        self.kizilou_leave_request = create_submitted_leave_request(
            self.kizilou, self.leave_type, "Κανονική άδεια kizilou", "2025-03-15", "2025-03-20"
        )
        
    def test_can_manager_approve_employee_request_by_department_manager(self):
        """
        Test: Department manager μπορεί να εγκρίνει αίτημα employee
        """
        can_approve = can_manager_approve(self.dept_manager, self.employee_leave_request)
        self.assertTrue(can_approve)
        
    def test_can_manager_approve_employee_request_by_kizilou(self):
        """
        Test: kizilou ΔΕΝ μπορεί να εγκρίνει αίτημα employee (wrong level)
        """
        can_approve = can_manager_approve(self.kizilou, self.employee_leave_request)
        self.assertFalse(can_approve)
        
    def test_can_manager_approve_department_manager_request_by_kizilou(self):
        """
        Test: kizilou μπορεί να εγκρίνει αίτημα department manager
        """
        can_approve = can_manager_approve(self.kizilou, self.dept_manager_leave_request)
        self.assertTrue(can_approve)
        
    def test_can_manager_approve_department_manager_request_by_employee(self):
        """
        Test: Employee ΔΕΝ μπορεί να εγκρίνει αίτημα department manager
        """
        can_approve = can_manager_approve(self.employee, self.dept_manager_leave_request)
        self.assertFalse(can_approve)
        
    def test_can_manager_approve_kizilou_request_by_delegkos(self):
        """
        Test: delegkos μπορεί να εγκρίνει αίτημα kizilou
        """
        can_approve = can_manager_approve(self.delegkos, self.kizilou_leave_request)
        self.assertTrue(can_approve)
        
    def test_can_manager_approve_own_request(self):
        """
        Test: User ΔΕΝ μπορεί να εγκρίνει το δικό του αίτημα
        """
        can_approve = can_manager_approve(self.employee, self.employee_leave_request)
        self.assertFalse(can_approve)
        
        can_approve = can_manager_approve(self.dept_manager, self.dept_manager_leave_request)
        self.assertFalse(can_approve)
        
    def test_can_manager_approve_with_none_user(self):
        """
        Test: None user ΔΕΝ μπορεί να εγκρίνει τίποτα
        """
        can_approve = can_manager_approve(None, self.employee_leave_request)
        self.assertFalse(can_approve)
        
    def test_can_manager_approve_with_none_request(self):
        """
        Test: None request ΔΕΝ μπορεί να εγκριθεί
        """
        can_approve = can_manager_approve(self.dept_manager, None)
        self.assertFalse(can_approve)
        
    def test_template_tag_in_template_context(self):
        """
        Test: Template tag λειτουργεί σωστά στο template context
        """
        template = Template(
            "{% load leave_permissions %}"
            "{% can_manager_approve user leave_request as can_approve %}"
            "{% if can_approve %}YES{% else %}NO{% endif %}"
        )
        
        # Test με department manager και employee request
        context = Context({
            'user': self.dept_manager,
            'leave_request': self.employee_leave_request
        })
        
        result = template.render(context)
        self.assertEqual(result, "YES")
        
        # Test με employee και department manager request
        context = Context({
            'user': self.employee,
            'leave_request': self.dept_manager_leave_request
        })
        
        result = template.render(context)
        self.assertEqual(result, "NO")
        
    def test_hierarchical_approval_template_logic(self):
        """
        Test: Ολόκληρη η hierarchical template logic
        """
        template = Template(
            "{% load leave_permissions %}"
            "{% can_manager_approve user leave_request as can_approve %}"
            "{% if can_approve %}"
            "<button class='approve-btn'>Έγκριση</button>"
            "{% endif %}"
        )
        
        # Employee request - department manager sees button
        context = Context({
            'user': self.dept_manager,
            'leave_request': self.employee_leave_request
        })
        result = template.render(context)
        self.assertIn("approve-btn", result)
        
        # Employee request - kizilou does NOT see button
        context = Context({
            'user': self.kizilou,
            'leave_request': self.employee_leave_request
        })
        result = template.render(context)
        self.assertNotIn("approve-btn", result)
        
        # Department manager request - kizilou sees button
        context = Context({
            'user': self.kizilou,
            'leave_request': self.dept_manager_leave_request
        })
        result = template.render(context)
        self.assertIn("approve-btn", result)
        
        # kizilou request - delegkos sees button
        context = Context({
            'user': self.delegkos,
            'leave_request': self.kizilou_leave_request
        })
        result = template.render(context)
        self.assertIn("approve-btn", result)
        
    def test_approved_request_no_approval_buttons(self):
        """
        Test: Εγκεκριμένο αίτημα δεν εμφανίζει κουμπιά έγκρισης
        """
        # Αλλαγή status σε APPROVED_MANAGER
        self.employee_leave_request.status = "PENDING_PROTOCOL"
        self.employee_leave_request.save()
        
        template = Template(
            "{% load leave_permissions %}"
            "{% if leave_request.status == 'SUBMITTED' %}"
            "{% can_manager_approve user leave_request as can_approve %}"
            "{% if can_approve %}"
            "<button class='approve-btn'>Έγκριση</button>"
            "{% endif %}"
            "{% endif %}"
        )
        
        context = Context({
            'user': self.dept_manager,
            'leave_request': self.employee_leave_request
        })
        result = template.render(context)
        self.assertNotIn("approve-btn", result)
        
    def test_leave_handler_permissions(self):
        """
        Test: Leave handler permissions
        """
        # Leave handler ΔΕΝ μπορεί να εγκρίνει (μόνο processing)
        can_approve = can_manager_approve(self.leave_handler, self.employee_leave_request)
        self.assertFalse(can_approve)
        
    def test_cross_department_approval_blocked(self):
        """
        Test: Cross-department approval είναι blocked
        """
        # Δημιουργία user από διαφορετικό τμήμα
        other_dept = self.pdede
        other_manager = User.objects.create_user(
            email="other@test.com",
            first_name="Other",
            last_name="Manager",
            department=other_dept,
            registration_status='APPROVED',
            is_active=True,
        )
        other_manager.roles.add(self.manager_role)
        
        # Other manager ΔΕΝ μπορεί να εγκρίνει employee request
        can_approve = can_manager_approve(other_manager, self.employee_leave_request)
        self.assertFalse(can_approve)
        
    def test_template_tag_performance(self):
        """
        Test: Template tag performance με πολλά requests
        """
        # Δημιουργία πολλών requests
        requests = []
        for i in range(10):
            request = create_submitted_leave_request(
                self.employee,
                self.leave_type,
                f"Request {i}",
                "2025-01-15",
                "2025-01-20",
            )
            requests.append(request)
        
        # Test ότι το template tag δεν έχει performance issues
        for request in requests:
            can_approve = can_manager_approve(self.dept_manager, request)
            self.assertTrue(can_approve)