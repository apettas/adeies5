"""Tests για canonical role codes και διαχωρισμό manager FK vs ρόλου."""
from django.test import TestCase

from accounts.models import Department, Role, User
from accounts.role_constants import ROLE_ADMIN, ROLE_EMPLOYEE, ROLE_MANAGER
from accounts.tests.test_data import TestDataMixin


class RoleConstantsTests(TestCase):
    def test_is_administrator_includes_superuser_and_admin_role(self):
        admin_role = Role.objects.create(code=ROLE_ADMIN, name='Διαχειριστής')
        user = User.objects.create_user(
            email='admin@test.com',
            first_name='Admin',
            last_name='User',
            registration_status='APPROVED',
            is_active=True,
        )
        user.roles.add(admin_role)
        self.assertTrue(user.is_administrator)

        superuser = User.objects.create_superuser(
            email='super@test.com',
            first_name='Super',
            last_name='User',
            password='pass',
        )
        self.assertTrue(superuser.is_administrator)

    def test_legacy_role_code_alias(self):
        role = Role.objects.create(code=ROLE_EMPLOYEE, name='Υπάλληλος')
        user = User.objects.create_user(
            email='emp@test.com',
            first_name='Emp',
            last_name='User',
            registration_status='APPROVED',
            is_active=True,
        )
        user.roles.add(role)
        self.assertTrue(user.has_role('employee'))
        self.assertTrue(user.has_role(ROLE_EMPLOYEE))


class ManagerAuthorityTests(TestDataMixin, TestCase):
    def test_is_manager_of_department_requires_fk(self):
        self.assertTrue(self.dept_manager.is_manager_of_department(self.child_department))
        self.assertTrue(self.dept_manager.is_assigned_department_manager)

        orphan = User.objects.create_user(
            email='orphan_mgr@test.com',
            first_name='Orphan',
            last_name='Manager',
            department=self.child_department,
            registration_status='APPROVED',
            is_active=True,
        )
        orphan.roles.add(self.manager_role)
        self.assertTrue(orphan.is_department_manager)
        self.assertFalse(orphan.is_manager_of_department(self.child_department))
        self.assertEqual(orphan.get_subordinates().count(), 0)

    def test_department_manager_save_adds_manager_role(self):
        employee = User.objects.create_user(
            email='newmgr@test.com',
            first_name='New',
            last_name='Manager',
            department=self.child_department,
            registration_status='APPROVED',
            is_active=True,
        )
        self.child_department.manager = employee
        self.child_department.save()
        employee.refresh_from_db()
        self.assertTrue(employee.has_role(ROLE_MANAGER))
