#!/usr/bin/env python
"""
Test script για τον έλεγχο της αφαίρεσης ημερών άδειας
"""

import os
import sys
import django
from django.conf import settings

# Ρύθμιση Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

from django.contrib.auth import get_user_model
from leaves.models import LeaveRequest, LeaveType, LeavePeriod
from datetime import date, timedelta
import logging

# Ενεργοποίηση logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

User = get_user_model()

def test_leave_balance_deduction():
    """Test για την αφαίρεση ημερών άδειας"""
    
    print("=== Test Leave Balance Deduction ===")
    
    # Βρίσκω τον χρήστη kotsonis
    try:
        user = User.objects.get(email='kotsonis@sch.gr')
        print(f"Βρέθηκε χρήστης: {user.first_name} {user.last_name} ({user.email})")
    except User.DoesNotExist:
        print("Χρήστης kotsonis δεν βρέθηκε")
        # Δοκιμάζω να βρω άλλον χρήστη
        users = User.objects.filter(is_active=True)[:5]
        if users:
            user = users[0]
            print(f"Χρησιμοποιώ εναλλακτικό χρήστη: {user.email}")
        else:
            print("Δεν βρέθηκε κανένας χρήστης")
            return
    
    # Βρίσκω τον τύπο κανονικής άδειας
    try:
        leave_type = LeaveType.objects.get(name='1 Κανονική Άδεια')
        print(f"Βρέθηκε τύπος άδειας: {leave_type.name}")
    except LeaveType.DoesNotExist:
        print("Τύπος άδειας '1 Κανονική Άδεια' δεν βρέθηκε")
        return
    
    # Εμφάνιση τρέχοντος υπολοίπου
    print(f"Τρέχον υπόλοιπο χρήστη: {user.leave_balance}")
    print(f"Carryover days: {user.carryover_leave_days}")
    print(f"Current year days: {user.current_year_leave_balance}")
    
    # Δημιουργία αίτησης άδειας
    leave_request = LeaveRequest.objects.create(
        user=user,
        leave_type=leave_type,
        description="Test αίτηση για έλεγχο αφαίρεσης ημερών",
        status='DRAFT'
    )
    
    # Δημιουργία περιόδου άδειας - 5 ημέρες
    period = LeavePeriod.objects.create(
        leave_request=leave_request,
        start_date=date.today() + timedelta(days=30),
        end_date=date.today() + timedelta(days=34)  # 5 ημέρες
    )
    
    print(f"Δημιουργήθηκε αίτηση με ID: {leave_request.id}")
    print(f"Σύνολο ημερών αίτησης: {leave_request.total_days}")
    
    # Test 1: Υποβολή αίτησης
    print("\n=== Test 1: Υποβολή αίτησης ===")
    try:
        result = leave_request.submit()
        print(f"Υποβολή αίτησης: {result}")
        print(f"Status μετά υποβολή: {leave_request.status}")
    except ValueError as e:
        print(f"Σφάλμα υποβολής: {e}")
        leave_request.delete()
        return
    
    # Test 2: Έγκριση από προϊστάμενο (προσομοίωση)
    print("\n=== Test 2: Έγκριση από προϊστάμενο ===")
    # Για την προσομοίωση, αλλάζω manually το status
    leave_request.status = 'APPROVED_MANAGER'
    leave_request.save()
    print(f"Status μετά έγκριση: {leave_request.status}")
    
    # Test 3: Ολοκλήρωση αίτησης
    print("\n=== Test 3: Ολοκλήρωση αίτησης ===")
    print(f"Υπόλοιπο ΠΡΙΝ την ολοκλήρωση: {user.leave_balance}")
    
    # Ανανέωση του user object από τη βάση
    user.refresh_from_db()
    print(f"Υπόλοιπο μετά refresh: {user.leave_balance}")
    
    # Προσομοίωση της ολοκλήρωσης
    leave_request.status = 'UNDER_PROCESSING'
    leave_request.save()
    
    result = leave_request.complete_by_handler(user, "Test completion")
    print(f"Ολοκλήρωση αίτησης: {result}")
    print(f"Status μετά ολοκλήρωση: {leave_request.status}")
    
    # Έλεγχος αν αφαιρέθηκαν οι ημέρες
    user.refresh_from_db()
    print(f"Υπόλοιπο ΜΕΤΑ την ολοκλήρωση: {user.leave_balance}")
    print(f"Carryover days μετά: {user.carryover_leave_days}")
    print(f"Current year days μετά: {user.current_year_leave_balance}")
    
    # Καθαρισμός - διαγραφή της test αίτησης
    leave_request.delete()
    print("\nΗ test αίτηση διαγράφηκε")

if __name__ == '__main__':
    test_leave_balance_deduction()