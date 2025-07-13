from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from accounts.models import Department, Role, Specialty
import random
from datetime import date, timedelta

User = get_user_model()

class Command(BaseCommand):
    help = 'Φορτώνει δοκιμαστικούς χρήστες στη βάση δεδομένων'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Έναρξη φόρτωσης χρηστών...'))
        
        # Φόρτωση χρηστών
        self.load_users()
        
        self.stdout.write(self.style.SUCCESS('Ολοκλήρωση φόρτωσης χρηστών!'))

    def load_users(self):
        """Φόρτωση χρηστών"""
        self.stdout.write('Φόρτωση χρηστών...')
        
        try:
            # Βρίσκω τα departments
            tmima_d = Department.objects.get(code='TMIMA_D')
            tmima_g = Department.objects.get(code='TMIMA_G')
            autotelous_dn = Department.objects.get(code='AUTOTELOUS_DN')
            
            # Βρίσκω τους ρόλους
            manager_role = Role.objects.get(code='MANAGER')
            employee_role = Role.objects.get(code='EMPLOYEE')
            leave_handler_role = Role.objects.get(code='LEAVE_HANDLER')
            
            # Βρίσκω τυχαίες ειδικότητες
            specialties = list(Specialty.objects.all())
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Σφάλμα κατά τη φόρτωση dependencies: {e}'))
            return
        
        users_data = [
            {
                'email': 'apettas@sch.gr',
                'first_name': 'Ανδρέας',
                'last_name': 'Πέττας',
                'password': '123',
                'department': tmima_d,
                'gender': 'MALE',
                'roles': [manager_role, leave_handler_role],
            },
            {
                'email': 'tolia@sch.gr',
                'first_name': 'Κορίνα',
                'last_name': 'Τόλια',
                'password': '123',
                'department': tmima_g,
                'gender': 'FEMALE',
                'roles': [manager_role, leave_handler_role],
            },
            {
                'email': 'korsianou@sch.gr',
                'first_name': 'Κατερίνα',
                'last_name': 'Κορσιάνου',
                'password': '123',
                'department': tmima_g,
                'gender': 'FEMALE',
                'roles': [employee_role, leave_handler_role],
            },
            {
                'email': 'fotopoulou@sch.gr',
                'first_name': 'Βάσω',
                'last_name': 'Φωτοπούλου',
                'password': '123',
                'department': tmima_g,
                'gender': 'FEMALE',
                'roles': [employee_role, leave_handler_role],
            },
            {
                'email': 'kizilou@sch.gr',
                'first_name': 'Όλγα',
                'last_name': 'Κυζίλου',
                'password': '123',
                'department': autotelous_dn,
                'gender': 'FEMALE',
                'roles': [manager_role],
            },
            {
                'email': 'kotsonis@sch.gr',
                'first_name': 'Ιωάννης',
                'last_name': 'Κοτσώνης',
                'password': '123',
                'department': tmima_d,
                'gender': 'MALE',
                'roles': [employee_role],
            },
            {
                'email': 'baladakis@sch.gr',
                'first_name': 'Βασίλειος',
                'last_name': 'Μπαλαδάκης',
                'password': '123',
                'department': tmima_d,
                'gender': 'MALE',
                'roles': [employee_role],
            },
            {
                'email': 'karayan@sch.gr',
                'first_name': 'Θεόδωρος',
                'last_name': 'Κάραγιαν',
                'password': '123',
                'department': tmima_d,
                'gender': 'MALE',
                'roles': [employee_role],
            }
        ]
        
        with transaction.atomic():
            for user_data in users_data:
                # Έλεγχος αν υπάρχει ήδη ο χρήστης
                if User.objects.filter(email=user_data['email']).exists():
                    self.stdout.write(f'  Χρήστης υπάρχει ήδη: {user_data["email"]}')
                    continue
                
                # Δημιουργία χρήστη
                user = User.objects.create_user(
                    email=user_data['email'],
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    password=user_data['password'],
                    department=user_data['department'],
                    gender=user_data['gender'],
                    # Τυχαίες τιμές για τα υπόλοιπα πεδία
                    phone=self.generate_random_phone(),
                    user_category=random.choice(['ADMINISTRATIVE', 'EDUCATIONAL']),
                    specialty=random.choice(specialties) if specialties else None,
                    hire_date=self.generate_random_hire_date(),
                    notification=f'Κοινοποίηση στο {user_data["department"].name}',
                    user_description=f'{user_data["first_name"]} {user_data["last_name"]} - {user_data["department"].name}',
                    registration_status='APPROVED',
                    is_active=True
                )
                
                # Προσθήκη ρόλων
                for role in user_data['roles']:
                    user.roles.add(role)
                
                self.stdout.write(f'  Δημιουργήθηκε χρήστης: {user.email} ({user.full_name})')
        
        self.stdout.write('Ολοκλήρωση φόρτωσης χρηστών.')

    def generate_random_phone(self):
        """Δημιουργία τυχαίου τηλεφώνου"""
        return f"26{random.randint(10, 99)}{random.randint(100000, 999999)}"

    def generate_random_hire_date(self):
        """Δημιουργία τυχαίας ημερομηνίας πρόσληψης"""
        start_date = date(2020, 1, 1)
        end_date = date(2024, 12, 31)
        time_between = end_date - start_date
        days_between = time_between.days
        random_days = random.randrange(days_between)
        return start_date + timedelta(days=random_days)