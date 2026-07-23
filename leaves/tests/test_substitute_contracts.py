"""Tests ροής συμβάσεων αναπληρωτών."""
from datetime import date

from django.test import TestCase
from django.urls import reverse

from accounts.models import EmployeeType
from accounts.tests.test_data import TestDataMixin
from leaves.models import LeaveType, SubstituteContract
from leaves.utils.balance_ledger import create_balance_entry, get_last_buckets
from leaves.utils.substitute_contracts import (
    activate_new_contract,
    end_contract,
    maybe_notify_handlers_on_reappearance,
)


class SubstituteContractFlowTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.substitute_type, _ = EmployeeType.objects.get_or_create(
            code='SUBSTITUTE', defaults={'name': 'Αναπληρωτές'},
        )
        self.employee.employee_type = self.substitute_type
        self.employee.annual_leave_entitlement = 10
        self.employee.current_regular_leave_balance = 0
        self.employee.substitute_leave_status = 'ACTIVE'
        self.employee.save()
        create_balance_entry(
            employee=self.employee,
            entry_type='INITIAL_BALANCE',
            description='Αρχικό',
            carryover_after=0,
            current_after=8,
            created_by=self.leave_handler,
        )
        self.leave_type = LeaveType.objects.create(
            name='Κανονική Test',
            code='REG_TEST',
            requires_approval=True,
            affects_regular_leave_balance=True,
            is_active=True,
        )

    def test_end_zeros_balance_and_blocks(self):
        end_contract(self.employee, self.leave_handler, notes='Λήξη 30/6')
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.substitute_leave_status, 'PENDING_CONTRACT')
        self.assertEqual(self.employee.current_regular_leave_balance, 0)
        self.assertTrue(self.employee.is_substitute_contract_blocked())
        self.assertFalse(self.employee.has_leave_request_permission())
        carry, current = get_last_buckets(self.employee)
        self.assertEqual((carry, current), (0, 0))

    def test_activate_grants_opening_equal_entitlement(self):
        end_contract(self.employee, self.leave_handler, notes='Λήξη')
        activate_new_contract(
            user=self.employee,
            contract_start=date(2026, 9, 1),
            contract_end=date(2027, 6, 30),
            entitled_days=12,
            notes='Νέα πρόσληψη',
            created_by=self.leave_handler,
            opening_balance=None,
        )
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.substitute_leave_status, 'ACTIVE')
        self.assertEqual(self.employee.annual_leave_entitlement, 12)
        self.assertEqual(self.employee.current_regular_leave_balance, 12)
        self.assertTrue(self.employee.has_leave_request_permission())
        self.assertTrue(
            SubstituteContract.objects.filter(user=self.employee, status='ACTIVE').exists()
        )

    def test_reappearance_notifies_once(self):
        end_contract(self.employee, self.leave_handler, notes='Λήξη')
        self.assertTrue(maybe_notify_handlers_on_reappearance(self.employee))
        self.assertFalse(maybe_notify_handlers_on_reappearance(self.employee))


class SubstituteContractViewTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.substitute_type, _ = EmployeeType.objects.get_or_create(
            code='SUBSTITUTE', defaults={'name': 'Αναπληρωτές'},
        )
        self.employee.employee_type = self.substitute_type
        self.employee.substitute_leave_status = 'PENDING_CONTRACT'
        self.employee.save()
        self.client.force_login(self.leave_handler)

    def test_handler_queue_ok(self):
        response = self.client.get(reverse('leaves:substitute_contracts'))
        self.assertEqual(response.status_code, 200)

    def test_pending_cannot_open_create(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse('leaves:create_leave_request'))
        self.assertEqual(response.status_code, 403)
