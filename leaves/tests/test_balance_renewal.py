"""Tests για FIFO κουβάδες, αλλαγή δικαιούμενων και ετήσια ανανέωση."""
from datetime import date
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import EmployeeType
from accounts.tests.test_data import TestDataMixin
from leaves.models import (
    BalanceRenewalSeason,
    BalanceRenewalSettings,
    BalanceRenewalUserStatus,
    RegularLeaveBalanceEntry,
)
from leaves.utils.balance_ledger import (
    apply_fifo_deduction,
    change_entitlement,
    create_balance_entry,
    deduct_leave_days,
    get_effective_entitlement,
    get_last_buckets,
)
from leaves.utils.balance_renewal import (
    apply_renewal_for_user,
    closing_year_for_date,
    is_apply_allowed,
    notify_users,
    refresh_season_statuses,
)


class FifoBucketTests(TestCase):
    def test_apply_fifo_deduction_order(self):
        carry, current, from_c, from_cur = apply_fifo_deduction(5, 10, 7)
        self.assertEqual((carry, current), (0, 8))
        self.assertEqual((from_c, from_cur), (5, 2))

    def test_apply_fifo_partial_carry(self):
        carry, current, from_c, from_cur = apply_fifo_deduction(5, 10, 3)
        self.assertEqual((carry, current), (2, 10))
        self.assertEqual((from_c, from_cur), (3, 0))


class BalanceLedgerBucketTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.administrative_type, _ = EmployeeType.objects.get_or_create(
            code='ADMINISTRATIVE', defaults={'name': 'Διοικητικοί'},
        )
        self.educational_type, _ = EmployeeType.objects.get_or_create(
            code='EDUCATIONAL', defaults={'name': 'Εκπαιδευτικοί'},
        )
        self.employee.employee_type = self.administrative_type
        self.employee.annual_leave_entitlement = 25
        self.employee.current_regular_leave_balance = 0
        self.employee.save()
        create_balance_entry(
            employee=self.employee,
            entry_type='INITIAL_BALANCE',
            description='Αρχικό',
            days_delta=30,
            carryover_after=5,
            current_after=25,
            created_by=self.leave_handler,
        )

    def test_deduct_uses_fifo(self):
        deduct_leave_days(self.employee, 7, created_by=self.leave_handler)
        carry, current = get_last_buckets(self.employee)
        self.assertEqual(carry, 0)
        self.assertEqual(current, 23)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.current_regular_leave_balance, 23)

    def test_entitlement_change_does_not_alter_balance(self):
        before = self.employee.current_regular_leave_balance
        change_entitlement(self.employee, 22, 'Διόρθωση προϋπηρεσίας', self.leave_handler)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.annual_leave_entitlement, 22)
        self.assertEqual(self.employee.current_regular_leave_balance, before)
        entry = RegularLeaveBalanceEntry.objects.filter(
            employee=self.employee, entry_type='ENTITLEMENT_CHANGE',
        ).latest('created_at')
        self.assertEqual(entry.old_entitlement, 25)
        self.assertEqual(entry.new_entitlement, 22)
        self.assertEqual(entry.days_delta, 0)

    def test_effective_entitlement_educational_fallback(self):
        self.employee.annual_leave_entitlement = 0
        self.employee.employee_type = self.educational_type
        self.employee.save()
        self.assertEqual(get_effective_entitlement(self.employee), 10)


class BalanceRenewalLogicTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.administrative_type, _ = EmployeeType.objects.get_or_create(
            code='ADMINISTRATIVE', defaults={'name': 'Διοικητικοί'},
        )
        self.employee.employee_type = self.administrative_type
        self.employee.annual_leave_entitlement = 25
        self.employee.registration_status = 'APPROVED'
        self.employee.is_active = True
        self.employee.save()
        create_balance_entry(
            employee=self.employee,
            entry_type='INITIAL_BALANCE',
            description='Αρχικό',
            carryover_after=3,
            current_after=10,
            created_by=self.leave_handler,
        )
        BalanceRenewalSettings.get_solo()

    def test_closing_year_and_apply_window(self):
        self.assertEqual(closing_year_for_date(date(2025, 12, 20)), 2025)
        self.assertEqual(closing_year_for_date(date(2026, 1, 15)), 2025)
        self.assertFalse(is_apply_allowed(date(2025, 12, 20), closing_year=2025))
        self.assertTrue(is_apply_allowed(date(2026, 1, 1), closing_year=2025))

    def test_apply_renewal_algorithm(self):
        season = BalanceRenewalSeason.objects.create(closing_year=2025)
        refresh_season_statuses(season)
        status = BalanceRenewalUserStatus.objects.get(season=season, user=self.employee)
        self.assertEqual(status.expiring_days, 3)
        self.assertEqual(status.carryover_days, 10)

        apply_renewal_for_user(status, self.leave_handler)
        carry, current = get_last_buckets(self.employee)
        self.assertEqual(carry, 10)
        self.assertEqual(current, 25)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.current_regular_leave_balance, 35)
        types = list(
            RegularLeaveBalanceEntry.objects.filter(employee=self.employee)
            .order_by('created_at')
            .values_list('entry_type', flat=True)
        )
        self.assertIn('CARRYOVER_EXPIRE', types)
        self.assertIn('CARRYOVER_IMPORT', types)
        self.assertIn('ANNUAL_GRANT', types)

    def test_notify_users_creates_notification(self):
        season = BalanceRenewalSeason.objects.create(closing_year=2025)
        refresh_season_statuses(season)
        count = notify_users(season, [self.employee.pk], self.leave_handler)
        self.assertEqual(count, 1)
        status = BalanceRenewalUserStatus.objects.get(season=season, user=self.employee)
        self.assertIsNotNone(status.notified_at)


class BalanceRenewalViewTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.leave_handler)
        BalanceRenewalSettings.get_solo()

    @patch('leaves.utils.balance_renewal.is_warning_period', return_value=False)
    def test_handler_can_open_renewal_page(self, _mock):
        response = self.client.get(reverse('leaves:balance_renewal'))
        self.assertEqual(response.status_code, 200)

    def test_employee_forbidden(self):
        self.client.force_login(self.employee)
        response = self.client.get(reverse('leaves:balance_renewal'))
        self.assertEqual(response.status_code, 403)

    def test_change_entitlement_view(self):
        self.employee.annual_leave_entitlement = 25
        self.employee.current_regular_leave_balance = 12
        self.employee.save()
        response = self.client.post(
            reverse('leaves:change_entitlement', kwargs={'user_id': self.employee.pk}),
            {'new_entitlement': '22', 'notes': 'Απόσπαση'},
        )
        self.assertEqual(response.status_code, 302)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.annual_leave_entitlement, 22)
        self.assertEqual(self.employee.current_regular_leave_balance, 12)
