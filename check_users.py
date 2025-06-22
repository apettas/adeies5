#!/usr/bin/env python
import os
import sys
import django

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

print('=== ΧΡΗΣΤΕΣ ΣΥΣΤΗΜΑΤΟΣ ===')
users = User.objects.all()
print(f'Συνολικοί χρήστες: {users.count()}')
print()

if users.count() == 0:
    print('❌ Δεν βρέθηκαν χρήστες στο σύστημα!')
else:
    for user in users:
        print(f'📧 Email: {user.email}')
        print(f'👤 Όνομα: {user.first_name} {user.last_name}')
        print(f'🔐 Superuser: {"Ναι" if user.is_superuser else "Όχι"}')
        print(f'✅ Ενεργός: {"Ναι" if user.is_active else "Όχι"}')
        print(f'🆔 Employee ID: {user.employee_id or "Δεν έχει οριστεί"}')
        
        roles = user.roles.all()
        if roles.exists():
            role_names = [role.name for role in roles]
            print(f'🎯 Ρόλοι: {", ".join(role_names)}')
        else:
            print('🎯 Ρόλοι: Κανένας')
        
        print('-' * 60)

print(f'\nΣτοιχεία σύνδεσης για το superuser:')
admin_user = User.objects.filter(email='admin@pdede.gr').first()
if admin_user:
    print('✅ Superuser admin@pdede.gr υπάρχει')
    print('🔑 Password: admin123')
else:
    print('❌ Superuser admin@pdede.gr ΔΕΝ υπάρχει!')