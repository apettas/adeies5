from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


def make_user(email, **extra):
    defaults = {
        'password': 'testpass123',
        'first_name': 'Test',
        'last_name': 'User',
    }
    defaults.update(extra)
    return User.objects.create_user(email=email, **defaults)


class LeaveBalanceIntegrationTestCase(TestCase):
    """Integration tests for the complete leave balance system."""

    def setUp(self):
        """Set up test data."""
        self.user = make_user(
            'test@example.com',
            first_name='Test',
            last_name='User',
            annual_leave_entitlement=25,
            carryover_leave_days=5,
            current_year_leave_balance=25,
        )

        self.user2 = make_user(
            'test2@example.com',
            first_name='Test',
            last_name='User2',
            annual_leave_entitlement=20,
            carryover_leave_days=3,
            current_year_leave_balance=18,
        )

    def test_full_leave_balance_workflow(self):
        """Test complete leave balance workflow from creation to usage."""
        self.assertEqual(self.user.leave_balance, 0)

        self.user.update_leave_balance()
        self.assertEqual(self.user.leave_balance, 30)

        self.assertTrue(self.user.can_request_leave_days(1))
        self.assertTrue(self.user.can_request_leave_days(15))
        self.assertTrue(self.user.can_request_leave_days(30))
        self.assertFalse(self.user.can_request_leave_days(31))

        success = self.user.use_leave_days(8)
        self.assertTrue(success)
        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.current_year_leave_balance, 22)
        self.assertEqual(self.user.leave_balance, 22)

        success = self.user.use_leave_days(23)
        self.assertFalse(success)
        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.current_year_leave_balance, 22)
        self.assertEqual(self.user.leave_balance, 22)

    def test_yearly_reset_workflow(self):
        """Test yearly reset functionality."""
        self.user.update_leave_balance()
        self.user.use_leave_days(10)

        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.current_year_leave_balance, 20)
        self.assertEqual(self.user.leave_balance, 20)

        self.user.reset_yearly_leave_balance()

        self.assertEqual(self.user.carryover_leave_days, 20)
        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.leave_balance, 45)

    def test_user_independence(self):
        """Test that users' leave balances are independent."""
        self.user.update_leave_balance()
        self.user2.update_leave_balance()

        self.assertEqual(self.user.leave_balance, 30)
        self.assertEqual(self.user2.leave_balance, 21)

        self.user.use_leave_days(15)
        self.assertEqual(self.user.leave_balance, 15)

        self.assertEqual(self.user2.leave_balance, 21)

        self.user2.use_leave_days(10)
        self.assertEqual(self.user2.leave_balance, 11)

        self.assertEqual(self.user.leave_balance, 15)

    def test_leave_balance_breakdown(self):
        """Test detailed leave balance breakdown."""
        self.user.update_leave_balance()

        breakdown = self.user.get_leave_balance_breakdown()
        expected = {
            'carryover_days': 5,
            'current_year_days': 25,
            'total_days': 30,
            'annual_entitlement': 25,
        }
        self.assertEqual(breakdown, expected)

        self.user.use_leave_days(8)
        breakdown = self.user.get_leave_balance_breakdown()
        expected = {
            'carryover_days': 0,
            'current_year_days': 22,
            'total_days': 22,
            'annual_entitlement': 25,
        }
        self.assertEqual(breakdown, expected)

    def test_multiple_operations_consistency(self):
        """Test consistency across multiple operations."""
        self.user.update_leave_balance()

        for days in (5, 3, 2):
            self.user.use_leave_days(days)

        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.current_year_leave_balance, 20)
        self.assertEqual(self.user.leave_balance, 20)

        breakdown = self.user.get_leave_balance_breakdown()
        self.assertEqual(
            breakdown['total_days'],
            breakdown['carryover_days'] + breakdown['current_year_days'],
        )

    def test_boundary_conditions(self):
        """Test boundary conditions and limits."""
        self.user.update_leave_balance()

        success = self.user.use_leave_days(30)
        self.assertTrue(success)
        self.assertEqual(self.user.leave_balance, 0)

        success = self.user.use_leave_days(1)
        self.assertFalse(success)
        self.assertEqual(self.user.leave_balance, 0)

        large_user = make_user(
            'large@example.com',
            annual_leave_entitlement=1000,
            carryover_leave_days=500,
            current_year_leave_balance=1000,
        )
        large_user.update_leave_balance()

        self.assertEqual(large_user.leave_balance, 1500)
        self.assertTrue(large_user.can_request_leave_days(1500))
        self.assertFalse(large_user.can_request_leave_days(1501))

    def test_reset_with_different_scenarios(self):
        """Test yearly reset under different scenarios."""
        self.user.update_leave_balance()
        self.user.use_leave_days(10)

        self.user.reset_yearly_leave_balance()

        self.assertEqual(self.user.carryover_leave_days, 20)
        self.assertEqual(self.user.current_year_leave_balance, 25)

        user_unused = make_user(
            'unused@example.com',
            annual_leave_entitlement=25,
            carryover_leave_days=5,
            current_year_leave_balance=25,
        )
        user_unused.update_leave_balance()
        user_unused.reset_yearly_leave_balance()

        self.assertEqual(user_unused.carryover_leave_days, 25)
        self.assertEqual(user_unused.current_year_leave_balance, 25)
        self.assertEqual(user_unused.leave_balance, 50)
