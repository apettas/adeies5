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


class LeaveBalanceTestCase(TestCase):
    """Test suite for leave balance calculation functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = make_user(
            'test@example.com',
            annual_leave_entitlement=25,
            carryover_leave_days=5,
            current_year_leave_balance=25,
        )

    def test_calculate_total_leave_balance_default(self):
        """Test calculation of total leave balance with default values."""
        user = make_user('default@example.com')

        self.assertEqual(user.calculate_total_leave_balance(), 0)
        self.assertEqual(user.leave_balance, 0)

    def test_calculate_total_leave_balance_with_values(self):
        """Test calculation of total leave balance with specific values."""
        total_balance = self.user.calculate_total_leave_balance()

        expected_balance = 5 + 25
        self.assertEqual(total_balance, expected_balance)
        self.user.update_leave_balance()
        self.assertEqual(self.user.leave_balance, expected_balance)

    def test_update_leave_balance_updates_field(self):
        """Test that update_leave_balance updates the leave_balance field."""
        self.assertEqual(self.user.leave_balance, 0)

        self.user.update_leave_balance()

        self.assertEqual(self.user.leave_balance, 30)

    def test_can_request_leave_days_sufficient_balance(self):
        """Test can_request_leave_days with sufficient balance."""
        self.user.update_leave_balance()

        self.assertTrue(self.user.can_request_leave_days(1))
        self.assertTrue(self.user.can_request_leave_days(15))
        self.assertTrue(self.user.can_request_leave_days(30))

    def test_can_request_leave_days_insufficient_balance(self):
        """Test can_request_leave_days with insufficient balance."""
        self.user.update_leave_balance()

        self.assertFalse(self.user.can_request_leave_days(31))
        self.assertFalse(self.user.can_request_leave_days(50))

    def test_can_request_leave_days_zero_balance(self):
        """Test can_request_leave_days with zero balance."""
        user = make_user(
            'zero@example.com',
            annual_leave_entitlement=0,
            carryover_leave_days=0,
            current_year_leave_balance=0,
        )
        user.update_leave_balance()

        self.assertFalse(user.can_request_leave_days(1))
        self.assertTrue(user.can_request_leave_days(0))

    def test_can_request_leave_days_negative_days(self):
        """Test can_request_leave_days with negative days."""
        self.user.update_leave_balance()

        self.assertTrue(self.user.can_request_leave_days(-1))
        self.assertTrue(self.user.can_request_leave_days(0))

    def test_use_leave_days_from_carryover_first(self):
        """Test that use_leave_days consumes carryover days first."""
        self.user.update_leave_balance()

        result = self.user.use_leave_days(3)

        self.assertTrue(result)
        self.assertEqual(self.user.carryover_leave_days, 2)
        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.leave_balance, 27)

    def test_use_leave_days_exhaust_carryover_then_current(self):
        """Test that use_leave_days exhausts carryover then uses current year."""
        self.user.update_leave_balance()

        result = self.user.use_leave_days(8)

        self.assertTrue(result)
        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.current_year_leave_balance, 22)
        self.assertEqual(self.user.leave_balance, 22)

    def test_use_leave_days_exact_balance(self):
        """Test using exact balance amount."""
        self.user.update_leave_balance()

        result = self.user.use_leave_days(30)

        self.assertTrue(result)
        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.current_year_leave_balance, 0)
        self.assertEqual(self.user.leave_balance, 0)

    def test_use_leave_days_insufficient_balance(self):
        """Test use_leave_days with insufficient balance."""
        self.user.update_leave_balance()

        result = self.user.use_leave_days(31)

        self.assertFalse(result)
        self.assertEqual(self.user.carryover_leave_days, 5)
        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.leave_balance, 30)

    def test_use_leave_days_zero_days(self):
        """Test use_leave_days with zero days."""
        self.user.update_leave_balance()

        result = self.user.use_leave_days(0)

        self.assertFalse(result)
        self.assertEqual(self.user.carryover_leave_days, 5)
        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.leave_balance, 30)

    def test_use_leave_days_negative_days(self):
        """Test use_leave_days with negative days."""
        self.user.update_leave_balance()

        result = self.user.use_leave_days(-5)

        self.assertFalse(result)
        self.assertEqual(self.user.carryover_leave_days, 5)
        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.leave_balance, 30)

    def test_reset_yearly_leave_balance(self):
        """Test yearly leave balance reset functionality."""
        self.user.current_year_leave_balance = 20
        self.user.carryover_leave_days = 3
        self.user.update_leave_balance()

        self.user.reset_yearly_leave_balance()

        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.carryover_leave_days, 20)
        self.assertEqual(self.user.leave_balance, 45)

    def test_reset_yearly_leave_balance_with_zero_current(self):
        """Test yearly reset with zero current year balance."""
        self.user.current_year_leave_balance = 0
        self.user.carryover_leave_days = 10
        self.user.update_leave_balance()

        self.user.reset_yearly_leave_balance()

        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.leave_balance, 25)

    def test_get_leave_balance_breakdown(self):
        """Test get_leave_balance_breakdown method."""
        self.user.update_leave_balance()

        breakdown = self.user.get_leave_balance_breakdown()

        expected_breakdown = {
            'carryover_days': 5,
            'current_year_days': 25,
            'total_days': 30,
            'annual_entitlement': 25,
        }

        self.assertEqual(breakdown, expected_breakdown)

    def test_get_leave_balance_breakdown_after_usage(self):
        """Test leave balance breakdown after using some days."""
        self.user.update_leave_balance()
        self.user.use_leave_days(8)

        breakdown = self.user.get_leave_balance_breakdown()

        expected_breakdown = {
            'carryover_days': 0,
            'current_year_days': 22,
            'total_days': 22,
            'annual_entitlement': 25,
        }

        self.assertEqual(breakdown, expected_breakdown)

    def test_multiple_users_leave_balance_independence(self):
        """Test that leave balance calculations are independent for different users."""
        user2 = make_user(
            'test2@example.com',
            first_name='Test',
            last_name='User2',
            annual_leave_entitlement=20,
            carryover_leave_days=3,
            current_year_leave_balance=15,
        )

        self.user.update_leave_balance()
        user2.update_leave_balance()

        self.assertEqual(self.user.leave_balance, 30)
        self.assertEqual(user2.leave_balance, 18)

        self.user.use_leave_days(10)

        self.assertEqual(self.user.leave_balance, 20)
        self.assertEqual(user2.leave_balance, 18)
