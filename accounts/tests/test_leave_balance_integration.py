"""
Integration tests για leave balance workflow μέσω ledger.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

from leaves.utils.balance_ledger import create_balance_entry, get_last_balance

User = get_user_model()


class LeaveBalanceIntegrationTests(TestCase):
    """Ολοκληρωμένα σενάρια υπολοίπου με ledger entries."""

    def setUp(self):
        self.user = User.objects.create_user(
            email='user1@test.com',
            first_name='User',
            last_name='One',
            registration_status='APPROVED',
            is_active=True,
            annual_leave_entitlement=25,
        )
        self.user2 = User.objects.create_user(
            email='user2@test.com',
            first_name='User',
            last_name='Two',
            registration_status='APPROVED',
            is_active=True,
            annual_leave_entitlement=25,
        )

    def _seed_balance(self, user, carryover=0, current_year=25):
        balance = carryover + current_year
        user.current_regular_leave_balance = balance
        user.save(update_fields=['current_regular_leave_balance'])
        if carryover:
            create_balance_entry(
                employee=user,
                entry_type='CARRYOVER_IMPORT',
                description='Μεταφορά προηγούμενου έτους',
                balance_after=carryover,
                days_delta=carryover,
            )
        create_balance_entry(
            employee=user,
            entry_type='INITIAL_BALANCE',
            description='Αρχικό υπόλοιπο',
            balance_after=balance,
            days_delta=current_year,
        )
        user.refresh_from_db()

    def test_full_leave_balance_workflow(self):
        """Πλήρες σενάριο: αρχικοποίηση, αφαίρεση, breakdown."""
        self._seed_balance(self.user, carryover=5, current_year=25)
        self.assertEqual(self.user.leave_balance, 30)

        create_balance_entry(
            employee=self.user,
            entry_type='LEAVE_GRANTED',
            description='Άδεια 8 ημερών',
            balance_after=22,
            days_delta=-8,
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.leave_balance, 22)

        breakdown = self.user.get_leave_balance_breakdown()
        self.assertEqual(breakdown['total_days'], 22)
        self.assertEqual(breakdown['carryover_days'], 5)
        self.assertEqual(breakdown['current_year_days'], 17)

    def test_multiple_users_independence(self):
        """Υπόλοιπα χρηστών είναι ανεξάρτητα."""
        self._seed_balance(self.user, carryover=5, current_year=25)
        self._seed_balance(self.user2, carryover=3, current_year=18)

        create_balance_entry(
            employee=self.user,
            entry_type='LEAVE_GRANTED',
            description='Άδεια',
            balance_after=15,
            days_delta=-15,
        )
        self.user.refresh_from_db()
        self.user2.refresh_from_db()

        self.assertEqual(self.user.leave_balance, 15)
        self.assertEqual(self.user2.leave_balance, 21)

    def test_insufficient_balance_check(self):
        """Δεν επιτρέπεται αίτηση πάνω από το διαθέσιμο υπόλοιπο."""
        self._seed_balance(self.user, carryover=0, current_year=30)
        self.assertTrue(self.user.can_request_leave_days(30))
        self.assertFalse(self.user.can_request_leave_days(31))

    def test_ledger_is_source_of_truth(self):
        """Το get_last_balance αντικατοπτρίζει τις εγγραφές ledger."""
        self._seed_balance(self.user, carryover=0, current_year=25)
        self.assertEqual(get_last_balance(self.user), 25)

        create_balance_entry(
            employee=self.user,
            entry_type='MANUAL_ADJUSTMENT',
            description='Διόρθωση',
            balance_after=20,
            days_delta=-5,
        )
        self.assertEqual(get_last_balance(self.user), 20)
