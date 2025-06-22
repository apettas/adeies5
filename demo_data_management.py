#!/usr/bin/env python3
"""
Demo script για το σύστημα διαχείρισης δεδομένων
ΠΔΕΔΕ Leave Management System

Αυτό το script δείχνει πώς να χρησιμοποιήσετε τα Django management commands
για τη διαχείριση στατικών και δυναμικών δεδομένων.
"""

import subprocess
import sys
import time


def run_command(cmd, description=""):
    """Εκτέλεση command με logging"""
    print(f"\n{'='*60}")
    print(f"🔧 {description}")
    print(f"Εκτέλεση: {cmd}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout:
            print("📤 Έξοδος:")
            print(result.stdout)
        if result.stderr:
            print("⚠️ Σφάλματα:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("✅ Επιτυχής εκτέλεση!")
        else:
            print(f"❌ Σφάλμα (exit code: {result.returncode})")
            
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Εξαίρεση: {e}")
        return False


def main():
    """Κύριο demo script"""
    print("🚀 DEMO: Σύστημα Διαχείρισης Δεδομένων ΠΔΕΔΕ")
    print("Αυτό το script θα δείξει τη χρήση των management commands")
    
    # Βήμα 1: Φόρτωση στατικών δεδομένων
    success = run_command(
        "docker-compose exec web python manage.py load_static_data",
        "ΒΗΜΑ 1: Φόρτωση στατικών δεδομένων"
    )
    if not success:
        print("❌ Αποτυχία φόρτωσης στατικών δεδομένων!")
        return
    
    time.sleep(2)
    
    # Βήμα 2: Έλεγχος τι έχει φορτωθεί
    run_command(
        "docker-compose exec web python manage.py shell -c \"from accounts.models import Role, Department; from leaves.models import LeaveType; print(f'Ρόλοι: {Role.objects.count()}'); print(f'Τμήματα: {Department.objects.count()}'); print(f'Τύποι αδειών: {LeaveType.objects.count()}')\"",
        "ΒΗΜΑ 2: Έλεγχος φορτωμένων στατικών δεδομένων"
    )
    
    time.sleep(2)
    
    # Βήμα 3: Καθαρισμός μόνο των χρηστών (demo)
    run_command(
        "docker-compose exec web python manage.py clear_dynamic_data --users --confirm",
        "ΒΗΜΑ 3: Καθαρισμός χρηστών (demo)"
    )
    
    time.sleep(2)
    
    # Βήμα 4: Πλήρης επαναφορά
    run_command(
        "docker-compose exec web python manage.py reset_database --force",
        "ΒΗΜΑ 4: Πλήρης επαναφορά βάσης δεδομένων"
    )
    
    time.sleep(2)
    
    # Βήμα 5: Τελικός έλεγχος
    run_command(
        "docker-compose exec web python manage.py shell -c \"from django.contrib.auth import get_user_model; from accounts.models import Role, Department; from leaves.models import LeaveType; User = get_user_model(); print('=== ΤΕΛΙΚΟΣ ΕΛΕΓΧΟΣ ==='); print(f'Χρήστες: {User.objects.count()}'); print(f'Ρόλοι: {Role.objects.count()}'); print(f'Τμήματα: {Department.objects.count()}'); print(f'Τύποι αδειών: {LeaveType.objects.count()}'); admin = User.objects.filter(email='admin@pdede.gr').first(); print(f'Superuser admin@pdede.gr: {'✅ Υπάρχει' if admin else '❌ Δεν υπάρχει'}')\"",
        "ΒΗΜΑ 5: Τελικός έλεγχος κατάστασης βάσης"
    )
    
    print(f"\n{'='*60}")
    print("🎉 DEMO ΟΛΟΚΛΗΡΩΘΗΚΕ!")
    print("📋 Περίληψη:")
    print("   ✅ Φόρτωση στατικών δεδομένων")
    print("   ✅ Καθαρισμός δυναμικών δεδομένων")
    print("   ✅ Πλήρης επαναφορά βάσης")
    print("   ✅ Διατήρηση superuser admin@pdede.gr")
    print(f"{'='*60}")
    
    print("\n📖 Για περισσότερες πληροφορίες:")
    print("   - Δείτε το DATA_MANAGEMENT.md")
    print("   - Χρησιμοποιήστε τα commands μεμονωμένα όπως χρειάζεται")
    

if __name__ == "__main__":
    main()