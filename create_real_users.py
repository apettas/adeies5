#!/usr/bin/env python
"""
Script δημιουργίας πραγματικών χρηστών για το σύστημα αδειών ΠΔΕΔΕ
Συμβατό με το ενημερωμένο schema (χωρίς employee_id, με νέα fields)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Department, Specialty, Role, DepartmentType, Headquarters, Prefecture

User = get_user_model()

print('=== ΔΗΜΙΟΥΡΓΙΑ ΧΡΗΣΤΩΝ (Ενημερωμένο Script) ===')

# ============================================================
# ΒΟΗΘΗΤΙΚΕΣ ΣΥΝΑΡΤΗΣΕΙΣ - Δημιουργία αντικειμένων αν δεν υπάρχουν
# ============================================================

def get_or_create_prefecture(code, name):
    """Βρίσκει ή δημιουργεί Νομό"""
    p, _ = Prefecture.objects.get_or_create(code=code, defaults={'name': name})
    return p

def get_or_create_headquarters(code, name):
    """Βρίσκει ή δημιουργεί Έδρα"""
    h, _ = Headquarters.objects.get_or_create(code=code, defaults={'name': name})
    return h

def get_or_create_department_type(code, name, description=''):
    """Βρίσκει ή δημιουργεί Τύπο Τμήματος"""
    dt, _ = DepartmentType.objects.get_or_create(
        code=code,
        defaults={'name': name, 'description': description}
    )
    return dt

def get_or_create_department(code, name, dept_type_code, dept_type_name, parent_code=None):
    """Βρίσκει ή δημιουργεί Τμήμα"""
    dept_type = get_or_create_department_type(dept_type_code, dept_type_name)
    parent = None
    if parent_code:
        try:
            parent = Department.objects.get(code=parent_code)
        except Department.DoesNotExist:
            print(f'  ⚠️  Γονικό τμήμα {parent_code} δεν βρέθηκε')
    
    dept, created = Department.objects.get_or_create(
        code=code,
        defaults={
            'name': name,
            'department_type': dept_type,
            'parent_department': parent,
        }
    )
    if created:
        print(f'  ✅ Νέο τμήμα: {name}')
    return dept

def get_or_create_specialty(short_name, full_name):
    """Βρίσκει ή δημιουργεί Ειδικότητα"""
    spec, created = Specialty.objects.get_or_create(
        specialties_short=short_name,
        defaults={'specialties_full': full_name}
    )
    if created:
        print(f'  ✅ Νέα ειδικότητα: {full_name}')
    return spec

def get_or_create_role(code, name, description=''):
    """Βρίσκει ή δημιουργεί Ρόλο"""
    role, created = Role.objects.get_or_create(
        code=code,
        defaults={'name': name, 'description': description}
    )
    if created:
        print(f'  ✅ Νέος ρόλος: {name}')
    return role


# ============================================================
# ΔΗΜΙΟΥΡΓΙΑ ΥΠΟΔΟΜΗΣ (Departments, Specialties, Roles)
# ============================================================

print('\n🏗️ Προετοιμασία υποδομής...')

# Νομοί & Έδρες
patra_pref = get_or_create_prefecture('ACH', 'Αχαΐα')
ilia_pref = get_or_create_prefecture('ILI', 'Ηλεία')
aitol_pref = get_or_create_prefecture('AIT', 'Αιτωλοακαρνανία')
patra_hq = get_or_create_headquarters('PATRA', 'Πάτρα')

# Βασικά τμήματα
pdede = get_or_create_department('PDEDE', 'ΠΔΕΔΕ', 'PDEDE', 'Περιφερειακή Διεύθυνση')
autotelous = get_or_create_department(
    'AUTOTELOUS_DN', 'ΑΥΤΟΤΕΛΗΣ ΔΙΕΥΘΥΝΣΗ',
    'AUTOTELOUS', 'Αυτοτελής Διεύθυνση', parent_code='PDEDE'
)
tmima_g = get_or_create_department(
    'TMIMA_G', 'ΤΜΗΜΑ Γ',
    'TMIMA_PDEDE', 'Τμήμα ΠΔΕΔΕ', parent_code='AUTOTELOUS_DN'
)
tmima_d = get_or_create_department(
    'TMIMA_D', 'ΤΜΗΜΑ Δ',
    'TMIMA_PDEDE', 'Τμήμα ΠΔΕΔΕ', parent_code='AUTOTELOUS_DN'
)

# Ειδικότητες
spec_dioikitikou = get_or_create_specialty('ΠΕ', 'ΠΕ Διοικητικού-Οικονομικού')
spec_daskaloi = get_or_create_specialty('ΠΕ70', 'ΠΕ70 ΔΑΣΚΑΛΟΙ')
spec_pliroforikis = get_or_create_specialty('ΠΕ86', 'ΠΕ86 ΠΛΗΡΟΦΟΡΙΚΗΣ')
spec_pe_pliro = get_or_create_specialty('ΠΕ', 'ΠΕ Πληροφορικής')

# Ρόλοι
role_manager = get_or_create_role('MANAGER', 'Προϊστάμενος', 'Προϊστάμενος τμήματος')
role_handler = get_or_create_role('LEAVE_HANDLER', 'Χειριστής Αδειών', 'Χειριστής αδειών ΠΔΕΔΕ')
role_employee = get_or_create_role('EMPLOYEE', 'Υπάλληλος', 'Απλός υπάλληλος')


# ============================================================
# ΔΕΔΟΜΕΝΑ ΧΡΗΣΤΩΝ
# ============================================================

users_data = [
    {
        'first_name': 'Ανδρέας',
        'last_name': 'Πέττας',
        'email': 'apettas@sch.gr',
        'department_code': 'TMIMA_D',
        'specialty_short': 'ΠΕ86',
        'role_code': 'MANAGER',
        'category': 'ADMINISTRATIVE',
        'phone1': '',
        'can_request_leave': True,
    },
    {
        'first_name': 'Κορίνα',
        'last_name': 'Τόλια',
        'email': 'tolia@sch.gr',
        'department_code': 'TMIMA_G',
        'specialty_short': 'ΠΕ',
        'role_code': 'MANAGER',
        'category': 'ADMINISTRATIVE',
        'phone1': '',
        'can_request_leave': True,
    },
    {
        'first_name': 'Όλγα',
        'last_name': 'Κιζίλου',
        'email': 'kizilou@sch.gr',
        'department_code': 'AUTOTELOUS_DN',
        'specialty_short': 'ΠΕ',
        'role_code': 'MANAGER',
        'category': 'ADMINISTRATIVE',
        'phone1': '',
        'can_request_leave': True,
    },
    {
        'first_name': 'Βασιλική',
        'last_name': 'Φωτοπούλου',
        'email': 'fotopoulou@sch.gr',
        'department_code': 'TMIMA_G',
        'specialty_short': 'ΠΕ70',
        'role_code': 'LEAVE_HANDLER',
        'category': 'EDUCATIONAL',
        'phone1': '',
        'can_request_leave': True,
    },
    {
        'first_name': 'Κατερίνα',
        'last_name': 'Κορσιάνου',
        'email': 'korsianou@sch.gr',
        'department_code': 'TMIMA_G',
        'specialty_short': 'ΠΕ',
        'role_code': 'LEAVE_HANDLER',
        'category': 'EDUCATIONAL',
        'phone1': '',
        'can_request_leave': True,
    },
    {
        'first_name': 'Ιωάννης',
        'last_name': 'Κοτσώνης',
        'email': 'kotsonis@sch.gr',
        'department_code': 'TMIMA_D',
        'specialty_short': 'ΠΕ86',
        'role_code': 'EMPLOYEE',
        'category': 'EDUCATIONAL',
        'phone1': '',
        'can_request_leave': True,
    },
    {
        'first_name': 'Θεόδωρος',
        'last_name': 'Καραγιάν',
        'email': 'karayan@sch.gr',
        'department_code': 'TMIMA_D',
        'specialty_short': 'ΠΕ',
        'role_code': 'EMPLOYEE',
        'category': 'ADMINISTRATIVE',
        'phone1': '',
        'can_request_leave': True,
    },
    {
        'first_name': 'Βασίλειος',
        'last_name': 'Μπαλαδάκης',
        'email': 'baladakis@sch.gr',
        'department_code': 'TMIMA_D',
        'specialty_short': 'ΠΕ86',
        'role_code': 'EMPLOYEE',
        'category': 'EDUCATIONAL',
        'phone1': '',
        'can_request_leave': True,
    }
]


# ============================================================
# ΔΗΜΙΟΥΡΓΙΑ ΧΡΗΣΤΩΝ
# ============================================================

print('\n👥 Δημιουργία χρηστών...')
created_users = []

for user_data in users_data:
    try:
        # Λήψη αντικειμένων από τη βάση (όχι hardcoded IDs!)
        department = Department.objects.get(code=user_data['department_code'])
        specialty = Specialty.objects.get(specialties_short=user_data['specialty_short'])
        role = Role.objects.get(code=user_data['role_code'])

        # Έλεγχος αν υπάρχει ήδη
        if User.objects.filter(email=user_data['email']).exists():
            print(f'⏭️  Υπάρχει ήδη: {user_data["first_name"]} {user_data["last_name"]} ({user_data["email"]})')
            continue

        # Δημιουργία χρήστη
        user = User.objects.create_user(
            email=user_data['email'],
            password='123',
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            department=department,
            specialty=specialty,
            user_category=user_data['category'],
            phone1=user_data.get('phone1', ''),
            can_request_leave=user_data.get('can_request_leave', True),
            can_approve_own_leave=False,
            is_active=True,
            registration_status='APPROVED',
            annual_leave_entitlement=25,
            carryover_leave_days=0,
            current_year_leave_balance=25,
            leave_balance=25,
            sick_leave_with_declaration=2,
            sick_days_current_year=0,
        )

        # Προσθήκη ρόλου
        user.roles.add(role)

        created_users.append(user)
        print(f'✅ {user.first_name} {user.last_name} - {user.email}')
        print(f'   🏢 {department.name} | 🎯 {specialty.specialties_full} | 👥 {role.name}')

    except Department.DoesNotExist:
        print(f'❌ Τμήμα {user_data["department_code"]} δεν βρέθηκε')
    except Specialty.DoesNotExist:
        print(f'❌ Ειδικότητα {user_data["specialty_short"]} δεν βρέθηκε')
    except Role.DoesNotExist:
        print(f'❌ Ρόλος {user_data["role_code"]} δεν βρέθηκε')
    except Exception as e:
        print(f'❌ Σφάλμα: {user_data["first_name"]} {user_data["last_name"]}: {e}')


# ============================================================
# ΑΠΟΤΕΛΕΣΜΑΤΑ
# ============================================================

print(f'\n📊 ΑΠΟΤΕΛΕΣΜΑΤΑ:')
print(f'✅ Δημιουργήθηκαν: {len(created_users)} χρήστες')
print(f'👥 Σύνολο χρηστών στο σύστημα: {User.objects.count()}')
print(f'🔐 Password για όλους: 123')

if created_users:
    from django.contrib.auth import authenticate
    test_user = created_users[0]
    auth_test = authenticate(email=test_user.email, password='123')
    print(f'\n🔐 Authentication test για {test_user.email}: {"✅ ΕΠΙΤΥΧΙΑ" if auth_test else "❌ ΑΠΟΤΥΧΙΑ"}')
