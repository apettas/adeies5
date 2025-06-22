#!/usr/bin/env python
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Department, Specialty, Role

User = get_user_model()

print('=== ΔΗΜΙΟΥΡΓΙΑ 8 ΠΡΑΓΜΑΤΙΚΩΝ ΧΡΗΣΤΩΝ ===')

# Mapping των departments
dept_mapping = {
    'ΤΜΗΜΑ Γ': 57,
    'ΤΜΗΜΑ Δ': 58, 
    'ΑΥΤΟΤΕΛΗΣ ΔΙΕΥΘΥΝΣΗ': 54
}

# Mapping των specialties
spec_mapping = {
    'ΠΕ Διοικητικού': 86,
    'ΠΕ70 ΔΑΣΚΑΛΟΙ': 88,
    'ΠΕ ΠΛΗΡΟΦΟΡΙΚΗΣ': 110,  # Χρήση ΆΛΛΗ ΕΙΔΙΚΟΤΗΤΑ
    'ΠΕ86 ΠΛΗΡΟΦΟΡΙΚΗΣ': 110  # Χρήση ΆΛΛΗ ΕΙΔΙΚΟΤΗΤΑ
}

# Mapping των roles
role_mapping = {
    'Προϊστάμενος': 17,
    'Χειριστής Αδειών': 18,  # Υπεύθυνος Προσωπικού
    'Υπάλληλος': 19
}

# Δεδομένα χρηστών
users_data = [
    {
        'first_name': 'Ανδρέας',
        'last_name': 'Πέττας',
        'email': 'apettas@sch.gr',
        'employee_id': 'EMP001',
        'department': 'ΤΜΗΜΑ Δ',
        'specialty': 'ΠΕ ΠΛΗΡΟΦΟΡΙΚΗΣ',
        'role': 'Προϊστάμενος',
        'category': 'ADMINISTRATIVE'
    },
    {
        'first_name': 'Κορίνα',
        'last_name': 'Τόλια',
        'email': 'tolia@sch.gr',
        'employee_id': 'EMP002',
        'department': 'ΤΜΗΜΑ Γ',
        'specialty': 'ΠΕ Διοικητικού',
        'role': 'Προϊστάμενος',
        'category': 'ADMINISTRATIVE'
    },
    {
        'first_name': 'Όλγα',
        'last_name': 'Κιζίλου',
        'email': 'kizilou@sch.gr',
        'employee_id': 'EMP003',
        'department': 'ΑΥΤΟΤΕΛΗΣ ΔΙΕΥΘΥΝΣΗ',
        'specialty': 'ΠΕ Διοικητικού',
        'role': 'Προϊστάμενος',
        'category': 'ADMINISTRATIVE'
    },
    {
        'first_name': 'Βασιλική',
        'last_name': 'Φωτοπούλου',
        'email': 'fotopoulou@sch.gr',
        'employee_id': 'EMP004',
        'department': 'ΤΜΗΜΑ Γ',
        'specialty': 'ΠΕ70 ΔΑΣΚΑΛΟΙ',
        'role': 'Χειριστής Αδειών',
        'category': 'EDUCATIONAL'
    },
    {
        'first_name': 'Κατερίνα',
        'last_name': 'Κορσιάνου',
        'email': 'korsianou@sch.gr',
        'employee_id': 'EMP005',
        'department': 'ΤΜΗΜΑ Γ',
        'specialty': 'ΠΕ Διοικητικού',
        'role': 'Χειριστής Αδειών',
        'category': 'EDUCATIONAL'
    },
    {
        'first_name': 'Ιωάννης',
        'last_name': 'Κοτσώνης',
        'email': 'kotsonis@sch.gr',
        'employee_id': 'EMP006',
        'department': 'ΤΜΗΜΑ Δ',
        'specialty': 'ΠΕ86 ΠΛΗΡΟΦΟΡΙΚΗΣ',
        'role': 'Υπάλληλος',
        'category': 'EDUCATIONAL'
    },
    {
        'first_name': 'Θεόδωρος',
        'last_name': 'Καραγιάν',
        'email': 'karayan@sch.gr',
        'employee_id': 'EMP007',
        'department': 'ΤΜΗΜΑ Δ',
        'specialty': 'ΠΕ ΠΛΗΡΟΦΟΡΙΚΗΣ',
        'role': 'Υπάλληλος',
        'category': 'ADMINISTRATIVE'
    },
    {
        'first_name': 'Βασίλειος',
        'last_name': 'Μπαλαδάκης',
        'email': 'baladakis@sch.gr',
        'employee_id': 'EMP008',
        'department': 'ΤΜΗΜΑ Δ',
        'specialty': 'ΠΕ86 ΠΛΗΡΟΦΟΡΙΚΗΣ',
        'role': 'Υπάλληλος',
        'category': 'EDUCATIONAL'
    }
]

print('🏗️ Δημιουργία χρηστών...')
created_users = []

for user_data in users_data:
    try:
        # Λήψη των αντικειμένων
        department = Department.objects.get(id=dept_mapping[user_data['department']])
        specialty = Specialty.objects.get(id=spec_mapping[user_data['specialty']])
        role = Role.objects.get(id=role_mapping[user_data['role']])
        
        # Δημιουργία χρήστη
        user = User.objects.create_user(
            email=user_data['email'],
            password='123',
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            employee_id=user_data['employee_id'],
            department=department,
            specialty=specialty,
            user_category=user_data['category'],
            is_active=True,
            registration_status='APPROVED'
        )
        
        # Προσθήκη ρόλου (ManyToMany field)
        user.roles.add(role)
        
        created_users.append(user)
        print(f'✅ {user.first_name} {user.last_name} - {user.email}')
        print(f'   🏢 {department.name} | 🎯 {specialty.specialties_full} | 👥 {role.name}')
        
    except Exception as e:
        print(f'❌ Σφάλμα δημιουργίας χρήστη {user_data["first_name"]} {user_data["last_name"]}: {e}')

print(f'\n📊 ΑΠΟΤΕΛΕΣΜΑΤΑ:')
print(f'✅ Δημιουργήθηκαν: {len(created_users)} χρήστες')
print(f'👥 Σύνολο χρηστών στο σύστημα: {User.objects.count()}')
print(f'🔐 Όλοι οι χρήστες έχουν password: 123')

# Επαλήθευση authentication για έναν χρήστη
if created_users:
    from django.contrib.auth import authenticate
    test_user = created_users[0]
    auth_test = authenticate(email=test_user.email, password='123')
    print(f'\n🔐 Authentication test για {test_user.email}: {"✅ ΕΠΙΤΥΧΙΑ" if auth_test else "❌ ΑΠΟΤΥΧΙΑ"}')