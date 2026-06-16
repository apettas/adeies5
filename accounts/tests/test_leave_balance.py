"""
Tests για ledger-based leave balance API στο User model.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from leaves.utils.balance_ledger import create_balance_entry, get_carryover_days

User = get_user_model()


class LeaveBalanceTests(TestCase):
    """Tests για υπόλοιπο αδειών μέσω ledger cache."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='balance@test.com',
            first_name='Test',
            last_name='User',
            registration_status='APPROVED',
            is_active=True,
            annual_leave_entitlement=25,
            current_regular_leave_balance=30,
        )
        create_balance_entry(
            employee=self.user,
            entry_type='CARRYOVER_IMPORT',
            description='Υπόλοιπο προηγούμενου έτους',
            balance_after=5,
            days_delta=5,
        )
        create_balance_entry(
            employee=self.user,
            entry_type='INITIAL_BALANCE',
            description='Αρχικό υπόλοιπο τρέχοντος έτους',
            balance_after=30,
            days_delta=25,
        )

    def test_leave_balance_property(self):
        """Το leave_balance property επιστρέφει το ledger cache."""
        self.assertEqual(self.user.leave_balance, 30)
        self.assertEqual(self.user.current_regular_leave_balance, 30)

    def test_can_request_leave_days(self):
        """Έλεγχος διαθεσιμότητας ημερών."""
        self.assertTrue(self.user.can_request_leave_days(30))
        self.assertTrue(self.user.can_request_leave_days(1))
        self.assertFalse(self.user.can_request_leave_days(31))

    def test_get_leave_balance_breakdown(self):
        """Αναλυτικό υπόλοιπο από ledger."""
        breakdown = self.user.get_leave_balance_breakdown()
        self.assertEqual(breakdown['total_days'], 30)
        self.assertEqual(breakdown['carryover_days'], 5)
        self.assertEqual(breakdown['current_year_days'], 25)
        self.assertEqual(breakdown['annual_entitlement'], 25)

    def test_deduction_via_ledger(self):
        """Αφαίρεση ημερών μέσω ledger entry."""
        create_balance_entry(
            employee=self.user,
            entry_type='LEAVE_GRANTED',
            description='Δοκιμαστική αφαίρεση',
            balance_after=22,
            days_delta=-8,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.leave_balance, 22)
        self.assertFalse(self.user.can_request_leave_days(23))

    def test_carryover_days_from_ledger(self):
        """Το carryover υπολογίζεται από CARRYOVER_IMPORT εγγραφές."""
        self.assertEqual(get_carryover_days(self.user), 5)

    def test_new_user_defaults(self):
        """Νέος χρήστης έχει μηδενικό υπόλοιπο."""
        user = User.objects.create_user(
            email='new@test.com',
            first_name='New',
            last_name='User',
            registration_status='APPROVED',
            is_active=True,
        )
        self.assertEqual(user.leave_balance, 0)
        breakdown = user.get_leave_balance_breakdown()
        self.assertEqual(breakdown['total_days'], 0)
        self.assertEqual(breakdown['carryover_days'], 0)
