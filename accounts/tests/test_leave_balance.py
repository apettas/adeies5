from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from decimal import Decimal

User = get_user_model()


class LeaveBalanceTestCase(TestCase):
    """Test suite for leave balance calculation functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            annual_leave_entitlement=25,
            carryover_leave_days=5,
            current_year_leave_balance=25
        )

    def test_calculate_total_leave_balance_default(self):
        """Test calculation of total leave balance with default values."""
        user = User.objects.create_user(
            username='defaultuser',
            email='default@example.com',
            password='testpass123'
        )
        
        # Default values should be 0
        self.assertEqual(user.calculate_total_leave_balance(), 0)
        self.assertEqual(user.leave_balance, 0)

    def test_calculate_total_leave_balance_with_values(self):
        """Test calculation of total leave balance with specific values."""
        total_balance = self.user.calculate_total_leave_balance()
        
        # Should be carryover_leave_days + current_year_leave_balance
        expected_balance = 5 + 25  # 30 days total
        self.assertEqual(total_balance, expected_balance)
        self.assertEqual(self.user.leave_balance, expected_balance)

    def test_update_leave_balance_updates_field(self):
        """Test that update_leave_balance updates the leave_balance field."""
        # Initially balance should be 0 (default)
        self.assertEqual(self.user.leave_balance, 0)
        
        # Update the balance
        self.user.update_leave_balance()
        
        # Balance should now be calculated value
        self.assertEqual(self.user.leave_balance, 30)

    def test_can_request_leave_days_sufficient_balance(self):
        """Test can_request_leave_days with sufficient balance."""
        self.user.update_leave_balance()
        
        # Should be able to request up to 30 days
        self.assertTrue(self.user.can_request_leave_days(1))
        self.assertTrue(self.user.can_request_leave_days(15))
        self.assertTrue(self.user.can_request_leave_days(30))

    def test_can_request_leave_days_insufficient_balance(self):
        """Test can_request_leave_days with insufficient balance."""
        self.user.update_leave_balance()
        
        # Should not be able to request more than 30 days
        self.assertFalse(self.user.can_request_leave_days(31))
        self.assertFalse(self.user.can_request_leave_days(50))

    def test_can_request_leave_days_zero_balance(self):
        """Test can_request_leave_days with zero balance."""
        user = User.objects.create_user(
            username='zerouser',
            email='zero@example.com',
            password='testpass123',
            annual_leave_entitlement=0,
            carryover_leave_days=0,
            current_year_leave_balance=0
        )
        user.update_leave_balance()
        
        self.assertFalse(user.can_request_leave_days(1))
        self.assertTrue(user.can_request_leave_days(0))

    def test_can_request_leave_days_negative_days(self):
        """Test can_request_leave_days with negative days."""
        self.user.update_leave_balance()
        
        # Should handle negative days gracefully
        self.assertTrue(self.user.can_request_leave_days(-1))
        self.assertTrue(self.user.can_request_leave_days(0))

    def test_use_leave_days_from_carryover_first(self):
        """Test that use_leave_days consumes carryover days first."""
        self.user.update_leave_balance()
        
        # Use 3 days - should come from carryover first
        result = self.user.use_leave_days(3)
        
        self.assertTrue(result)
        self.assertEqual(self.user.carryover_leave_days, 2)  # 5 - 3 = 2
        self.assertEqual(self.user.current_year_leave_balance, 25)  # unchanged
        self.assertEqual(self.user.leave_balance, 27)  # 2 + 25 = 27

    def test_use_leave_days_exhaust_carryover_then_current(self):
        """Test that use_leave_days exhausts carryover then uses current year."""
        self.user.update_leave_balance()
        
        # Use 8 days - should exhaust carryover (5) then use current year (3)
        result = self.user.use_leave_days(8)
        
        self.assertTrue(result)
        self.assertEqual(self.user.carryover_leave_days, 0)  # exhausted
        self.assertEqual(self.user.current_year_leave_balance, 22)  # 25 - 3 = 22
        self.assertEqual(self.user.leave_balance, 22)  # 0 + 22 = 22

    def test_use_leave_days_exact_balance(self):
        """Test using exact balance amount."""
        self.user.update_leave_balance()
        
        # Use all 30 days
        result = self.user.use_leave_days(30)
        
        self.assertTrue(result)
        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.current_year_leave_balance, 0)
        self.assertEqual(self.user.leave_balance, 0)

    def test_use_leave_days_insufficient_balance(self):
        """Test use_leave_days with insufficient balance."""
        self.user.update_leave_balance()
        
        # Try to use 31 days (more than available 30)
        result = self.user.use_leave_days(31)
        
        self.assertFalse(result)
        # Values should remain unchanged
        self.assertEqual(self.user.carryover_leave_days, 5)
        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.leave_balance, 30)

    def test_use_leave_days_zero_days(self):
        """Test use_leave_days with zero days."""
        self.user.update_leave_balance()
        
        result = self.user.use_leave_days(0)
        
        self.assertTrue(result)
        # Values should remain unchanged
        self.assertEqual(self.user.carryover_leave_days, 5)
        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.leave_balance, 30)

    def test_use_leave_days_negative_days(self):
        """Test use_leave_days with negative days."""
        self.user.update_leave_balance()
        
        result = self.user.use_leave_days(-5)
        
        # Should handle negative days gracefully by treating as 0
        self.assertTrue(result)
        self.assertEqual(self.user.carryover_leave_days, 5)
        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.leave_balance, 30)

    def test_reset_yearly_leave_balance(self):
        """Test yearly leave balance reset functionality."""
        # Set up user with used leave days
        self.user.current_year_leave_balance = 20  # 5 days used
        self.user.carryover_leave_days = 3  # some carryover
        self.user.update_leave_balance()
        
        # Reset yearly balance
        self.user.reset_yearly_leave_balance()
        
        # Current year balance should be reset to entitlement
        self.assertEqual(self.user.current_year_leave_balance, 25)
        # Previous current year balance should become carryover
        self.assertEqual(self.user.carryover_leave_days, 20)
        # Total balance should be recalculated
        self.assertEqual(self.user.leave_balance, 45)  # 20 + 25

    def test_reset_yearly_leave_balance_with_zero_current(self):
        """Test yearly reset with zero current year balance."""
        self.user.current_year_leave_balance = 0
        self.user.carryover_leave_days = 10
        self.user.update_leave_balance()
        
        self.user.reset_yearly_leave_balance()
        
        self.assertEqual(self.user.current_year_leave_balance, 25)
        self.assertEqual(self.user.carryover_leave_days, 0)  # 0 becomes carryover
        self.assertEqual(self.user.leave_balance, 25)

    def test_get_leave_balance_breakdown(self):
        """Test get_leave_balance_breakdown method."""
        self.user.update_leave_balance()
        
        breakdown = self.user.get_leave_balance_breakdown()
        
        expected_breakdown = {
            'carryover_days': 5,
            'current_year_days': 25,
            'total_days': 30,
            'annual_entitlement': 25
        }
        
        self.assertEqual(breakdown, expected_breakdown)

    def test_get_leave_balance_breakdown_after_usage(self):
        """Test leave balance breakdown after using some days."""
        self.user.update_leave_balance()
        self.user.use_leave_days(8)  # Uses 5 carryover + 3 current
        
        breakdown = self.user.get_leave_balance_breakdown()
        
        expected_breakdown = {
            'carryover_days': 0,
            'current_year_days': 22,
            'total_days': 22,
            'annual_entitlement': 25
        }
        
        self.assertEqual(breakdown, expected_breakdown)

    def test_leave_balance_with_decimal_values(self):
        """Test leave balance calculations with decimal values."""
        user = User.objects.create_user(
            username='decimaluser',
            email='decimal@example.com',
            password='testpass123',
            annual_leave_entitlement=25,
            carryover_leave_days=2.5,
            current_year_leave_balance=22.5
        )
        user.update_leave_balance()
        
        self.assertEqual(user.leave_balance, 25.0)
        self.assertTrue(user.can_request_leave_days(2.5))
        self.assertFalse(user.can_request_leave_days(25.5))

    def test_leave_balance_automatic_calculation_on_save(self):
        """Test that leave balance is automatically calculated when carryover or current year balance changes."""
        # Change carryover days
        self.user.carryover_leave_days = 10
        self.user.save()
        
        # Leave balance should be automatically updated
        self.assertEqual(self.user.leave_balance, 35)  # 10 + 25
        
        # Change current year balance
        self.user.current_year_leave_balance = 20
        self.user.save()
        
        # Leave balance should be automatically updated
        self.assertEqual(self.user.leave_balance, 30)  # 10 + 20

    def test_leave_balance_validation_negative_values(self):
        """Test validation for negative values."""
        user = User.objects.create_user(
            username='negativeuser',
            email='negative@example.com',
            password='testpass123',
            annual_leave_entitlement=25,
            carryover_leave_days=-5,  # negative carryover
            current_year_leave_balance=25
        )
        user.update_leave_balance()
        
        # Should handle negative values gracefully
        self.assertEqual(user.leave_balance, 20)  # -5 + 25 = 20

    def test_multiple_users_leave_balance_independence(self):
        """Test that leave balance calculations are independent for different users."""
        user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123',
            annual_leave_entitlement=20,
            carryover_leave_days=3,
            current_year_leave_balance=15
        )
        
        self.user.update_leave_balance()
        user2.update_leave_balance()
        
        self.assertEqual(self.user.leave_balance, 30)  # 5 + 25
        self.assertEqual(user2.leave_balance, 18)  # 3 + 15
        
        # Use leave days for one user
        self.user.use_leave_days(10)
        
        # Other user should be unaffected
        self.assertEqual(self.user.leave_balance, 20)
        self.assertEqual(user2.leave_balance, 18)