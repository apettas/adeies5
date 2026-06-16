"""Test data mixins για KEDASY/SDEY workflow paths."""
from accounts.models import Department, DepartmentType, Role
from django.contrib.auth import get_user_model

from accounts.tests.test_data import TestDataMixin

User = get_user_model()


class KedasyWorkflowMixin(TestDataMixin):
    """Επεκτείνει TestDataMixin με KEDASY, SDEY, γραμματεία."""

    def setUp(self):
        super().setUp()

        self.kedasy_dept_type = DepartmentType.objects.create(
            name='ΚΕΔΑΣΥ',
            code='KEDASY',
            description='Κεντρική Διεύθυνση',
        )
        self.sdey_dept_type = DepartmentType.objects.create(
            name='ΣΔΕΥ',
            code='SDEY',
            description='Σχολική Διεύθυνση',
        )
        self.secretary_role = Role.objects.create(
            name='Γραμματεία',
            code='SECRETARY',
        )

        self.kedasy_dept = Department.objects.create(
            name='ΚΕΔΑΣΥ Δυτικής Ελλάδας',
            code='KEDASY_WGR',
            department_type=self.kedasy_dept_type,
            headquarters=self.headquarters,
            prefecture=self.prefecture,
        )
        self.sdey_dept = Department.objects.create(
            name='ΣΔΕΥ Πάτρας',
            code='SDEY_PAT',
            department_type=self.sdey_dept_type,
            parent_department=self.kedasy_dept,
            headquarters=self.headquarters,
            prefecture=self.prefecture,
        )

        self.kedasy_secretary = User.objects.create_user(
            email='kedasy_secretary@test.com',
            first_name='Γραμματέας',
            last_name='ΚΕΔΑΣΥ',
            department=self.kedasy_dept,
            registration_status='APPROVED',
            is_active=True,
        )
        self.kedasy_secretary.roles.add(self.secretary_role)

        self.kedasy_manager = User.objects.create_user(
            email='kedasy_manager@test.com',
            first_name='Προϊστάμενος',
            last_name='ΚΕΔΑΣΥ',
            department=self.kedasy_dept,
            registration_status='APPROVED',
            is_active=True,
        )
        self.kedasy_manager.roles.add(self.manager_role)

        self.kedasy_employee = User.objects.create_user(
            email='kedasy_employee@test.com',
            first_name='Υπάλληλος',
            last_name='ΚΕΔΑΣΥ',
            department=self.kedasy_dept,
            registration_status='APPROVED',
            is_active=True,
            current_regular_leave_balance=25,
        )
        self.kedasy_employee.roles.add(self.employee_role)

        self.sdey_employee = User.objects.create_user(
            email='sdey_employee@test.com',
            first_name='Εκπαιδευτικός',
            last_name='ΣΔΕΥ',
            department=self.sdey_dept,
            registration_status='APPROVED',
            is_active=True,
            current_regular_leave_balance=25,
        )
        self.sdey_employee.roles.add(self.employee_role)

        self.kedasy_dept.manager = self.kedasy_manager
        self.kedasy_dept.save()
