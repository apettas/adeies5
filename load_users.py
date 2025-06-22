#!/usr/bin/env python
import os
import sys
import django

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Role, Department

User = get_user_model()

print('=== ΕΝΗΜΕΡΩΣΗ ADMIN USER ===')
# Ενημέρωση admin user με τους νέους ρόλους
admin = User.objects.get(email='admin@pdede.gr')
all_roles = Role.objects.all()
admin.roles.clear()
admin.roles.set(all_roles)
print(f'✅ Admin user ενημερώθηκε με {all_roles.count()} ρόλους')

print('\n=== ΔΗΜΙΟΥΡΓΙΑ ΝΕΩΝ ΧΡΗΣΤΩΝ ===')

# Βοηθητικά objects
leave_handler_role = Role.objects.get(code='LEAVE_HANDLER')
manager_role = Role.objects.get(code='MANAGER') 
employee_role = Role.objects.get(code='EMPLOYEE')

dept_primary = Department.objects.get(name='Τμήμα Πρωτοβάθμιας Εκπαίδευσης')  # Γ
dept_secondary = Department.objects.get(name='Τμήμα Δευτεροβάθμιας Εκπαίδευσης')  # Δ
dept_autonomous = Department.objects.get(name='Αυτοτελής Διεύθυνση Εκπαίδευσης')

# Δημιουργία χρηστών
users_data = [
    {
        'email': 'apettas@sch.gr',
        'first_name': 'Ανδρέας',
        'last_name': 'Πέττας',
        'password': '123',
        'department': dept_secondary,
        'roles': [manager_role, leave_handler_role],
        'employee_id': 'AP001'
    },
    {
        'email': 'tolia@sch.gr',
        'first_name': 'Κορίνα',
        'last_name': 'Τόλια',
        'password': '123',
        'department': dept_primary,
        'roles': [manager_role, leave_handler_role],
        'employee_id': 'KT001'
    },
    {
        'email': 'korsianou@sch.gr',
        'first_name': 'Κατερίνα',
        'last_name': 'Κορσιάνου',
        'password': '123',
        'department': dept_primary,
        'roles': [employee_role, leave_handler_role],
        'employee_id': 'KK001'
    },
    {
        'email': 'fotopoulou@sch.gr',
        'first_name': 'Βάσω',
        'last_name': 'Φωτοπούλου',
        'password': '123',
        'department': dept_primary,
        'roles': [employee_role, leave_handler_role],
        'employee_id': 'VF001'
    },
    {
        'email': 'kizilou@sch.gr',
        'first_name': 'Όλγα',
        'last_name': 'Κυζίλου',
        'password': '123',
        'department': dept_autonomous,
        'roles': [manager_role],
        'employee_id': 'OK001'
    },
    {
        'email': 'kotsonis@sch.gr',
        'first_name': 'Ιωάννης',
        'last_name': 'Κοτσώνης',
        'password': '123',
        'department': dept_secondary,
        'roles': [employee_role],
        'employee_id': 'IK001'
    },
    {
        'email': 'baladakis@sch.gr',
        'first_name': 'Βασίλειος',
        'last_name': 'Μπαλαδάκης',
        'password': '123',
        'department': dept_secondary,
        'roles': [employee_role],
        'employee_id': 'VB001'
    },
    {
        'email': 'karayan@sch.gr',
        'first_name': 'Θεόδωρος',
        'last_name': 'Κάραγιαν',
        'password': '123',
        'department': dept_secondary,
        'roles': [employee_role],
        'employee_id': 'TK001'
    }
]

for user_data in users_data:
    user = User.objects.create_user(
        email=user_data['email'],
        password=user_data['password'],
        first_name=user_data['first_name'],
        last_name=user_data['last_name'],
        employee_id=user_data['employee_id'],
        department=user_data['department']
    )
    user.roles.set(user_data['roles'])
    role_names = [role.name for role in user_data['roles']]
    print(f'✅ {user.first_name} {user.last_name} - {user.email}')
    print(f'   Τμήμα: {user.department.name}')
    print(f'   Ρόλοι: {", ".join(role_names)}')
    print()

print(f'Δημιουργήθηκαν {len(users_data)} νέοι χρήστες!')