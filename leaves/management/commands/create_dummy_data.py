from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Department
from leaves.models import LeaveType, LeaveRequest
from datetime import date, timedelta
import random

User = get_user_model()


class Command(BaseCommand):
    help = 'Δημιουργία dummy δεδομένων για δοκιμές'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Δημιουργία dummy δεδομένων...'))
        
        # Δημιουργία Τμημάτων
        self.create_departments()
        
        # Δημιουργία Τύπων Αδειών
        self.create_leave_types()
        
        # Δημιουργία Χρηστών
        self.create_users()
        
        # Δημιουργία Δοκιμαστικών Αιτήσεων
        self.create_sample_requests()
        
        self.stdout.write(self.style.SUCCESS('Τα dummy δεδομένα δημιουργήθηκαν επιτυχώς!'))

    def create_departments(self):
        """Δημιουργία της οργανωτικής δομής"""
        self.stdout.write('Δημιουργία τμημάτων...')
        
        # Κύρια Διεύθυνση
        main_direction, created = Department.objects.get_or_create(
            code='PDEDE',
            defaults={
                'name': 'Περιφερειακή Διεύθυνση Εκπαίδευσης Δυτικής Ελλάδας'
            }
        )
        
        # Τμήματα
        departments_data = [
            ('TMIMA_A', 'Τμήμα Α'),
            ('TMIMA_B', 'Τμήμα Β'),
            ('TMIMA_C', 'Τμήμα Γ'),
            ('TMIMA_D', 'Τμήμα Δ'),
            ('GRAF_NOM', 'Γραφείο Νομικής'),
        ]
        
        for code, name in departments_data:
            Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name
                }
            )
        
        self.stdout.write(self.style.SUCCESS('Τμήματα δημιουργήθηκαν!'))

    def create_leave_types(self):
        """Δημιουργία τύπων αδειών"""
        self.stdout.write('Δημιουργία τύπων αδειών...')
        
        leave_types_data = [
            ('Κανονική Άδεια', 'Ετήσια κανονική άδεια', 25, False),
            ('Άδεια Ασθενείας', 'Άδεια για λόγους υγείας', 30, True),
            ('Άδεια Μητρότητας', 'Άδεια μητρότητας', 119, True),
            ('Άδεια Πατρότητας', 'Άδεια πατρότητας', 14, True),
            ('Ειδική Άδεια', 'Ειδική άδεια για προσωπικούς λόγους', 6, True),
            ('Εκπαιδευτική Άδεια', 'Άδεια για εκπαιδευτικούς σκοπούς', 30, True),
        ]
        
        for name, description, max_days, requires_approval in leave_types_data:
            LeaveType.objects.get_or_create(
                name=name,
                defaults={
                    'description': description,
                    'max_days': max_days,
                    'requires_approval': requires_approval,
                }
            )
        
        self.stdout.write(self.style.SUCCESS('Τύποι αδειών δημιουργήθηκαν!'))

    def create_users(self):
        """Δημιουργία χρηστών"""
        self.stdout.write('Δημιουργία χρηστών...')
        
        # Τμήματα
        tmima_d = Department.objects.get(code='TMIMA_D')
        tmima_a = Department.objects.get(code='TMIMA_A')
        main_direction = Department.objects.get(code='PDEDE')
        
        # Διαχειριστής
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'first_name': 'Διαχειριστής',
                'last_name': 'Συστήματος',
                'email': 'admin@pdede.gov.gr',
                'role': 'administrator',
                'department': main_direction,
                'is_staff': True,
                'is_superuser': True,
                'employee_id': 'ADM001'
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
        
        # Προϊστάμενος Τμήματος Δ - Ανδρέας Πέττας
        manager_d, created = User.objects.get_or_create(
            username='a.pettas',
            defaults={
                'first_name': 'Ανδρέας',
                'last_name': 'Πέττας',
                'email': 'a.pettas@pdede.gov.gr',
                'role': 'department_manager',
                'department': tmima_d,
                'employee_id': 'MGR001',
                'phone': '2610-123456'
            }
        )
        if created:
            manager_d.set_password('manager123')
            manager_d.save()
        
        # Υπάλληλος Τμήματος Δ - Κοτσώνης Ιωάννης
        employee_d, created = User.objects.get_or_create(
            username='i.kotsonis',
            defaults={
                'first_name': 'Ιωάννης',
                'last_name': 'Κοτσώνης',
                'email': 'i.kotsonis@pdede.gov.gr',
                'role': 'employee',
                'department': tmima_d,
                'manager': manager_d,
                'employee_id': 'EMP001',
                'phone': '2610-123457'
            }
        )
        if created:
            employee_d.set_password('employee123')
            employee_d.save()
        
        # Χειριστής Αδειών - Φωτοπούλου Βασιλική
        handler, created = User.objects.get_or_create(
            username='v.fotopoulou',
            defaults={
                'first_name': 'Βασιλική',
                'last_name': 'Φωτοπούλου',
                'email': 'v.fotopoulou@pdede.gov.gr',
                'role': 'leave_handler',
                'department': main_direction,
                'employee_id': 'HND001',
                'phone': '2610-123458'
            }
        )
        if created:
            handler.set_password('handler123')
            handler.save()
        
        # Επιπλέον χρήστες για δοκιμές
        # Προϊστάμενος Τμήματος Α
        manager_a, created = User.objects.get_or_create(
            username='manager.a',
            defaults={
                'first_name': 'Μαρία',
                'last_name': 'Παπαδοπούλου',
                'email': 'manager.a@pdede.gov.gr',
                'role': 'department_manager',
                'department': tmima_a,
                'employee_id': 'MGR002'
            }
        )
        if created:
            manager_a.set_password('manager123')
            manager_a.save()
        
        # Υπάλληλος Τμήματος Α
        employee_a, created = User.objects.get_or_create(
            username='employee.a',
            defaults={
                'first_name': 'Δημήτρης',
                'last_name': 'Νικολάου',
                'email': 'employee.a@pdede.gov.gr',
                'role': 'employee',
                'department': tmima_a,
                'manager': manager_a,
                'employee_id': 'EMP002'
            }
        )
        if created:
            employee_a.set_password('employee123')
            employee_a.save()
        
        self.stdout.write(self.style.SUCCESS('Χρήστες δημιουργήθηκαν!'))

    def create_sample_requests(self):
        """Δημιουργία δοκιμαστικών αιτήσεων"""
        self.stdout.write('Δημιουργία δοκιμαστικών αιτήσεων...')
        
        # Χρήστες
        try:
            employee_d = User.objects.get(username='i.kotsonis')
            employee_a = User.objects.get(username='employee.a')
            manager_d = User.objects.get(username='a.pettas')
            handler = User.objects.get(username='v.fotopoulou')
        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING('Δεν βρέθηκαν χρήστες για δοκιμαστικές αιτήσεις'))
            return
        
        # Τύποι αδειών
        try:
            regular_leave = LeaveType.objects.get(name='Κανονική Άδεια')
            sick_leave = LeaveType.objects.get(name='Άδεια Ασθενείας')
        except LeaveType.DoesNotExist:
            self.stdout.write(self.style.WARNING('Δεν βρέθηκαν τύποι αδειών'))
            return
        
        # Αίτηση 1: Υποβληθείσα αίτηση (περιμένει έγκριση)
        start_date = date.today() + timedelta(days=30)
        end_date = start_date + timedelta(days=4)
        
        request1, created = LeaveRequest.objects.get_or_create(
            user=employee_d,
            leave_type=regular_leave,
            start_date=start_date,
            end_date=end_date,
            defaults={
                'description': 'Αίτηση για οικογενειακές υποχρεώσεις',
                'status': 'SUBMITTED'
            }
        )
        
        # Αίτηση 2: Εγκεκριμένη από προϊστάμενο (περιμένει επεξεργασία)
        start_date2 = date.today() + timedelta(days=60)
        end_date2 = start_date2 + timedelta(days=9)
        
        request2, created = LeaveRequest.objects.get_or_create(
            user=employee_d,
            leave_type=regular_leave,
            start_date=start_date2,
            end_date=end_date2,
            defaults={
                'description': 'Καλοκαιρινή άδεια',
                'status': 'APPROVED_MANAGER',
                'manager_approved_by': manager_d,
                'manager_comments': 'Εγκρίθηκε'
            }
        )
        
        # Αίτηση 3: Ολοκληρωμένη αίτηση
        start_date3 = date.today() - timedelta(days=30)
        end_date3 = start_date3 + timedelta(days=2)
        
        request3, created = LeaveRequest.objects.get_or_create(
            user=employee_d,
            leave_type=sick_leave,
            start_date=start_date3,
            end_date=end_date3,
            defaults={
                'description': 'Άδεια ασθενείας',
                'status': 'COMPLETED',
                'manager_approved_by': manager_d,
                'processed_by': handler,
                'manager_comments': 'Εγκρίθηκε',
                'processing_comments': 'Ολοκληρώθηκε',
                'protocol_number': 'ΠΔΕΔΕ/001/2024'
            }
        )
        
        self.stdout.write(self.style.SUCCESS('Δοκιμαστικές αιτήσεις δημιουργήθηκαν!'))

    def create_superuser_if_not_exists(self):
        """Δημιουργία superuser αν δεν υπάρχει"""
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@pdede.gov.gr',
                password='admin123',
                first_name='Διαχειριστής',
                last_name='Συστήματος'
            )
            self.stdout.write(self.style.SUCCESS('Δημιουργήθηκε superuser: admin/admin123'))