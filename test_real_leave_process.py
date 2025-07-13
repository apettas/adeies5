#!/usr/bin/env python
"""
Test script για τη δοκιμή της πραγματικής διαδικασίας αίτησης άδειας
"""

import os
import sys
import django
from django.conf import settings

# Ρύθμιση Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

from accounts.models import User
from leaves.models import LeaveRequest, LeaveType, LeavePeriod
from leaves.views import submit_final_request, complete_leave_request
from django.test import RequestFactory
from django.contrib.auth.models import AnonymousUser
from datetime import date, timedelta
import logging

# Ενεργοποίηση logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_real_leave_process():
    """Test για την πραγματική διαδικασία αίτησης άδειας"""
    
    print("=== Test Real Leave Process ===")
    
    # Βρίσκω τον χρήστη kotsonis
    user = User.objects.get(email='kotsonis@sch.gr')
    print(f"Χρήστης: {user.first_name} {user.last_name}")
    print(f"Υπόλοιπο ΠΡΙΝ: {user.leave_balance}")
    
    # Βρίσκω τον τύπο κανονικής άδειας
    leave_type = LeaveType.objects.get(name='1 Κανονική Άδεια')
    
    # Δημιουργία αίτησης άδειας
    leave_request = LeaveRequest.objects.create(
        user=user,
        leave_type=leave_type,
        description="Test αίτηση μέσω πραγματικής διαδικασίας",
        status='DRAFT'
    )
    
    # Δημιουργία περιόδου άδειας - 3 ημέρες
    period = LeavePeriod.objects.create(
        leave_request=leave_request,
        start_date=date.today() + timedelta(days=20),
        end_date=date.today() + timedelta(days=22)  # 3 ημέρες
    )
    
    print(f"\nΔημιουργήθηκε αίτηση με ID: {leave_request.id}")
    print(f"Σύνολο ημερών αίτησης: {leave_request.total_days}")
    
    # Test 1: Υποβολή μέσω model method
    print("\n=== Test 1: Υποβολή μέσω model method ===")
    try:
        result = leave_request.submit()
        print(f"Αποτέλεσμα υποβολής: {result}")
        print(f"Status μετά υποβολή: {leave_request.status}")
        user.refresh_from_db()
        print(f"Υπόλοιπο μετά υποβολή: {user.leave_balance}")
    except Exception as e:
        print(f"Σφάλμα υποβολής: {e}")
        leave_request.delete()
        return
    
    # Test 2: Προσομοίωση έγκρισης
    print("\n=== Test 2: Προσομοίωση έγκρισης ===")
    leave_request.status = 'APPROVED_MANAGER'
    leave_request.save()
    print(f"Status μετά έγκριση: {leave_request.status}")
    
    # Test 3: Ολοκλήρωση μέσω view
    print("\n=== Test 3: Ολοκλήρωση μέσω view ===")
    user.refresh_from_db()
    print(f"Υπόλοιπο ΠΡΙΝ ολοκλήρωση: {user.leave_balance}")
    
    # Προσομοίωση ολοκλήρωσης
    leave_request.status = 'UNDER_PROCESSING'
    leave_request.save()
    
    # Καλούμε τη μέθοδο complete_by_handler
    handler = User.objects.filter(roles__code='LEAVE_HANDLER').first()
    if not handler:
        handler = user  # Fallback
    
    result = leave_request.complete_by_handler(handler, "Test completion via real process")
    print(f"Αποτέλεσμα ολοκλήρωσης: {result}")
    print(f"Status μετά ολοκλήρωση: {leave_request.status}")
    
    # Έλεγχος αποτελέσματος
    user.refresh_from_db()
    print(f"Υπόλοιπο ΜΕΤΑ ολοκλήρωση: {user.leave_balance}")
    
    # Αναλυτικά στοιχεία
    breakdown = user.get_leave_balance_breakdown()
    print(f"\nΑναλυτικά στοιχεία:")
    print(f"- Προηγούμενο έτος: {breakdown['carryover_days']}")
    print(f"- Τρέχον έτος: {breakdown['current_year_days']}")
    print(f"- Σύνολο: {breakdown['total_days']}")
    print(f"- Ετήσιο δικαίωμα: {breakdown['annual_entitlement']}")
    
    # Καθαρισμός
    leave_request.delete()
    print("\nΗ test αίτηση διαγράφηκε")

if __name__ == '__main__':
    test_real_leave_process()