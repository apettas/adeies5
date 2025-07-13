"""
Test data setup for hierarchical approval system tests
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.models import Department, Role, Headquarters, Prefecture, DepartmentType

User = get_user_model()


class TestDataMixin:
    """
    Mixin για δημιουργία test data για hierarchical approval system
    """
    
    def setUp(self):
        """
        Δημιουργία test data:
        - Departments (AUTOTELOUS_DN, PDEDE)
        - Users (employee, dept_manager, kizilou, delegkos)
        - Hierarchical structure
        """
        super().setUp()
        
        # Δημιουργία Headquarters και Prefecture
        self.headquarters = Headquarters.objects.create(
            name="Κεντρικά Γραφεία",
            code="HQ001"
        )
        
        self.prefecture = Prefecture.objects.create(
            name="Αττικής",
            code="ATT001"
        )
        
        # Δημιουργία DepartmentTypes
        self.autotelous_dept_type = DepartmentType.objects.create(
            name="Αυτοτελής Διεύθυνση",
            code="AUTOTELOUS",
            description="Τύπος αυτοτελούς διεύθυνσης"
        )
        
        self.pdede_dept_type = DepartmentType.objects.create(
            name="Περιφερειακή Διεύθυνση Εκπαίδευσης",
            code="PDEDE_MAIN",
            description="Τύπος περιφερειακής διεύθυνσης εκπαίδευσης"
        )
        
        # Δημιουργία Departments
        self.autotelous_dn = Department.objects.create(
            name="Αυτοτελής Διεύθυνση Διοικητικής, Οικονομικής και Παιδαγωγικής Υποστήριξης",
            code="AUTOTELOUS_DN",
            department_type=self.autotelous_dept_type,
            headquarters=self.headquarters,
            prefecture=self.prefecture
        )
        
        self.pdede = Department.objects.create(
            name="Περιφερειακή Διεύθυνση Εκπαίδευσης Δυτικής Ελλάδας",
            code="PDEDE",
            department_type=self.pdede_dept_type,
            headquarters=self.headquarters,
            prefecture=self.prefecture
        )
        
        # Δημιουργία child department κάτω από AUTOTELOUS_DN
        self.child_dept_type = DepartmentType.objects.create(
            name="Παιδαγωγικό Τμήμα",
            code="PEDAGOGICAL",
            description="Τύπος παιδαγωγικού τμήματος"
        )
        
        self.child_department = Department.objects.create(
            name="Παιδαγωγικό Τμήμα",
            code="PEDAGOGICAL_DEPT",
            department_type=self.child_dept_type,
            parent_department=self.autotelous_dn,
            headquarters=self.headquarters,
            prefecture=self.prefecture
        )
        
        # Δημιουργία Roles
        self.employee_role = Role.objects.create(
            name="Υπάλληλος",
            code="EMPLOYEE"
        )
        
        self.manager_role = Role.objects.create(
            name="Προϊστάμενος",
            code="MANAGER"
        )
        
        self.leave_handler_role = Role.objects.create(
            name="Χειριστής Αδειών",
            code="LEAVE_HANDLER"
        )
        
        # Δημιουργία Test Users
        # 1. Employee στο child department
        self.employee = User.objects.create_user(
            email="employee@test.com",
            first_name="Υπάλληλος",
            last_name="Τεστ",
            department=self.child_department,
            registration_status='APPROVED',
            is_active=True
        )
        self.employee.roles.add(self.employee_role)
        
        # 2. Department Manager του child department
        self.dept_manager = User.objects.create_user(
            email="dept_manager@test.com",
            first_name="Προϊστάμενος",
            last_name="Τμήματος",
            department=self.child_department,
            registration_status='APPROVED',
            is_active=True
        )
        self.dept_manager.roles.add(self.manager_role)
        
        # 3. kizilou (προϊστάμενος AUTOTELOUS_DN)
        self.kizilou = User.objects.create_user(
            email="kizilou@test.com",
            first_name="Κιζίλου",
            last_name="Τεστ",
            department=self.autotelous_dn,
            registration_status='APPROVED',
            is_active=True
        )
        self.kizilou.roles.add(self.manager_role)
        
        # 4. delegkos (προϊστάμενος PDEDE)
        self.delegkos = User.objects.create_user(
            email="delegkos@test.com",
            first_name="Δελέγκος",
            last_name="Τεστ",
            department=self.pdede,
            registration_status='APPROVED',
            is_active=True
        )
        self.delegkos.roles.add(self.manager_role)
        
        # 5. Leave Handler
        self.leave_handler = User.objects.create_user(
            email="leave_handler@test.com",
            first_name="Χειριστής",
            last_name="Αδειών",
            department=self.pdede,
            registration_status='APPROVED',
            is_active=True
        )
        self.leave_handler.roles.add(self.leave_handler_role)
        
        # Ρύθμιση ιεραρχίας - Managers για κάθε τμήμα
        # child_department manager: dept_manager
        self.child_department.manager = self.dept_manager
        self.child_department.save()
        
        # autotelous_dn manager: kizilou
        self.autotelous_dn.manager = self.kizilou
        self.autotelous_dn.save()
        
        # pdede manager: delegkos
        self.pdede.manager = self.delegkos
        self.pdede.save()
        
    def tearDown(self):
        """
        Καθαρισμός test data
        """
        User.objects.all().delete()
        Department.objects.all().delete()
        Role.objects.all().delete()
        DepartmentType.objects.all().delete()
        Headquarters.objects.all().delete()
        Prefecture.objects.all().delete()
        super().tearDown()