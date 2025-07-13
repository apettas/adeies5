from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal

User = get_user_model()


class LeaveBalanceIntegrationTestCase(TestCase):
    """Integration tests for the complete leave balance system."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            annual_leave_entitlement=25,
            carryover_leave_days=5,
            current_year_leave_balance=25
        )
        
        # Create a second user for independence testing
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User2',
            annual_leave_entitlement=20,
            carryover_leave_days=3,
            current_year_leave_balance=18
        )

    def test_full_leave_balance_workflow(self):
        """Test complete leave balance workflow from creation to usage."""
        # Initial state
        self.assertEqual(self.user.leave_balance, 0)  # Default value
        
        # Update balance
        self.user.update_leave_balance()
        self.assertEqual(self.user.leave_balance, 30)  # 5 + 25
        
        # Check if user can request various amounts
        self.assertTrue(self.user.can_request_leave_days(1))
        self.assertTrue(self.user.can_request_leave_days(15))
        self.assertTrue(self.user.can_request_leave_days(30))
        self.assertFalse(self.user.can_request_leave_days(31))
        
        # Use some leave days (should consume carryover first)
        success = self.user.use_leave_days(8)
        self.assertTrue(success)
        self.assertEqual(self.user.carryover_leave_days, 0)  # All 5 used
        self.assertEqual(self.user.current_year_leave_balance, 22)  # 3 used from current year
        self.assertEqual(self.user.leave_balance, 22)  # 0 + 22
        
        # Try to use more than available
        success = self.user.use_leave_days(23)
        self.assertFalse(success)
        # Values should remain unchanged
        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.current_year_leave_balance, 22)
        self.assertEqual(self.user.leave_balance, 22)

    def test_yearly_reset_workflow(self):
        """Test yearly reset functionality."""
        # Set up initial state
        self.user.update_leave_balance()
        self.user.use_leave_days(10)  # Use 10 days
        
        # Should have 5 carryover - 5 = 0, 25 current - 5 = 20, total = 20
        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.current_year_leave_balance, 20)
        self.assertEqual(self.user.leave_balance, 20)
        
        # Reset yearly balance
        self.user.reset_yearly_leave_balance()
        
        # Current year balance becomes carryover, new current year is reset to entitlement
        self.assertEqual(self.user.carryover_leave_days, 20)  # Previous current year
        self.assertEqual(self.user.current_year_leave_balance, 25)  # Reset to entitlement
        self.assertEqual(self.user.leave_balance, 45)  # 20 + 25

    def test_user_independence(self):
        """Test that users' leave balances are independent."""
        self.user.update_leave_balance()
        self.user2.update_leave_balance()
        
        # Initial balances
        self.assertEqual(self.user.leave_balance, 30)  # 5 + 25
        self.assertEqual(self.user2.leave_balance, 21)  # 3 + 18
        
        # User 1 uses leave days
        self.user.use_leave_days(15)
        self.assertEqual(self.user.leave_balance, 15)
        
        # User 2 should be unaffected
        self.assertEqual(self.user2.leave_balance, 21)
        
        # User 2 uses leave days
        self.user2.use_leave_days(10)
        self.assertEqual(self.user2.leave_balance, 11)
        
        # User 1 should be unaffected
        self.assertEqual(self.user.leave_balance, 15)

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Test with zero values
        user_zero = User.objects.create_user(
            username='zerouser',
            email='zero@example.com',
            password='testpass123',
            annual_leave_entitlement=0,
            carryover_leave_days=0,
            current_year_leave_balance=0
        )
        user_zero.update_leave_balance()
        
        self.assertEqual(user_zero.leave_balance, 0)
        self.assertFalse(user_zero.can_request_leave_days(1))
        self.assertTrue(user_zero.can_request_leave_days(0))
        
        # Test with negative values
        user_negative = User.objects.create_user(
            username='negativeuser',
            email='negative@example.com',
            password='testpass123',
            annual_leave_entitlement=25,
            carryover_leave_days=-5,
            current_year_leave_balance=25
        )
        user_negative.update_leave_balance()
        
        self.assertEqual(user_negative.leave_balance, 20)  # -5 + 25
        
        # Test using negative days (should be handled gracefully)
        self.user.update_leave_balance()
        result = self.user.use_leave_days(-5)
        self.assertTrue(result)  # Should handle gracefully
        self.assertEqual(self.user.leave_balance, 30)  # Should remain unchanged

    def test_leave_balance_breakdown(self):
        """Test detailed leave balance breakdown."""
        self.user.update_leave_balance()
        
        breakdown = self.user.get_leave_balance_breakdown()
        expected = {
            'carryover_days': 5,
            'current_year_days': 25,
            'total_days': 30,
            'annual_entitlement': 25
        }
        self.assertEqual(breakdown, expected)
        
        # After using some days
        self.user.use_leave_days(8)
        breakdown = self.user.get_leave_balance_breakdown()
        expected = {
            'carryover_days': 0,
            'current_year_days': 22,
            'total_days': 22,
            'annual_entitlement': 25
        }
        self.assertEqual(breakdown, expected)

    def test_decimal_precision(self):
        """Test handling of decimal values in leave calculations."""
        user_decimal = User.objects.create_user(
            username='decimaluser',
            email='decimal@example.com',
            password='testpass123',
            annual_leave_entitlement=25,
            carryover_leave_days=2.5,
            current_year_leave_balance=22.5
        )
        user_decimal.update_leave_balance()
        
        self.assertEqual(user_decimal.leave_balance, 25.0)
        self.assertTrue(user_decimal.can_request_leave_days(2.5))
        self.assertTrue(user_decimal.can_request_leave_days(25.0))
        self.assertFalse(user_decimal.can_request_leave_days(25.5))
        
        # Use half days
        success = user_decimal.use_leave_days(3.0)
        self.assertTrue(success)
        self.assertEqual(user_decimal.carryover_leave_days, 0)  # 2.5 used, 0.5 remaining from carryover
        self.assertEqual(user_decimal.current_year_leave_balance, 22.0)  # 0.5 used from current year
        self.assertEqual(user_decimal.leave_balance, 22.0)

    def test_automatic_balance_calculation_on_save(self):
        """Test that leave balance is recalculated when relevant fields change."""
        # Initial balance
        self.user.update_leave_balance()
        self.assertEqual(self.user.leave_balance, 30)
        
        # Change carryover days
        self.user.carryover_leave_days = 10
        self.user.save()
        
        # Balance should be automatically updated
        self.assertEqual(self.user.leave_balance, 35)  # 10 + 25
        
        # Change current year balance
        self.user.current_year_leave_balance = 20
        self.user.save()
        
        # Balance should be automatically updated
        self.assertEqual(self.user.leave_balance, 30)  # 10 + 20

    def test_multiple_operations_consistency(self):
        """Test consistency across multiple operations."""
        self.user.update_leave_balance()
        
        # Perform multiple operations
        operations = [
            ('use', 5),
            ('use', 3),
            ('use', 2),
        ]
        
        for operation, days in operations:
            if operation == 'use':
                self.user.use_leave_days(days)
        
        # Total used: 10 days
        # Should have consumed all 5 carryover + 5 from current year
        self.assertEqual(self.user.carryover_leave_days, 0)
        self.assertEqual(self.user.current_year_leave_balance, 20)
        self.assertEqual(self.user.leave_balance, 20)
        
        # Verify breakdown consistency
        breakdown = self.user.get_leave_balance_breakdown()
        self.assertEqual(breakdown['total_days'], 
                        breakdown['carryover_days'] + breakdown['current_year_days'])

    def test_boundary_conditions(self):
        """Test boundary conditions and limits."""
        self.user.update_leave_balance()
        
        # Test exact balance usage
        success = self.user.use_leave_days(30)
        self.assertTrue(success)
        self.assertEqual(self.user.leave_balance, 0)
        
        # Test cannot use more when balance is zero
        success = self.user.use_leave_days(1)
        self.assertFalse(success)
        self.assertEqual(self.user.leave_balance, 0)
        
        # Test very large numbers
        large_user = User.objects.create_user(
            username='largeuser',
            email='large@example.com',
            password='testpass123',
            annual_leave_entitlement=1000,
            carryover_leave_days=500,
            current_year_leave_balance=1000
        )
        large_user.update_leave_balance()
        
        self.assertEqual(large_user.leave_balance, 1500)
        self.assertTrue(large_user.can_request_leave_days(1500))
        self.assertFalse(large_user.can_request_leave_days(1501))

    def test_error_handling(self):
        """Test error handling and validation."""
        self.user.update_leave_balance()
        
        # Test invalid inputs
        result = self.user.use_leave_days(None)
        self.assertFalse(result)  # Should handle gracefully
        
        # Test with string input (should be converted or handled)
        try:
            result = self.user.use_leave_days("5")
            # Should either work (if converted) or fail gracefully
            self.assertIsInstance(result, bool)
        except (TypeError, ValueError):
            # Expected if no conversion is implemented
            pass

    def test_reset_with_different_scenarios(self):
        """Test yearly reset under different scenarios."""
        # Scenario 1: User has used all carryover but some current year remains
        self.user.update_leave_balance()
        self.user.use_leave_days(10)  # Uses all carryover (5) + 5 from current
        
        self.user.reset_yearly_leave_balance()
        
        self.assertEqual(self.user.carryover_leave_days, 20)  # Previous current year balance
        self.assertEqual(self.user.current_year_leave_balance, 25)  # Reset to entitlement
        
        # Scenario 2: User has used nothing
        user_unused = User.objects.create_user(
            username='unuseduser',
            email='unused@example.com',
            password='testpass123',
            annual_leave_entitlement=25,
            carryover_leave_days=5,
            current_year_leave_balance=25
        )
        user_unused.update_leave_balance()
        user_unused.reset_yearly_leave_balance()
        
        self.assertEqual(user_unused.carryover_leave_days, 25)  # Full current year carries over
        self.assertEqual(user_unused.current_year_leave_balance, 25)  # Reset to entitlement
        self.assertEqual(user_unused.leave_balance, 50)  # 25 + 25