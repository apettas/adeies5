from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Department
from leaves.models import LeaveType, LeaveRequest
from notifications.models import Notification

User = get_user_model()


class Command(BaseCommand):
    help = 'Καθαρισμός όλων των δεδομένων και δημιουργία νέων dummy users'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Καθαρισμός όλων των δεδομένων...'))
        
        # Καθαρισμός δεδομένων
        self.clean_all_data()
        
        # Δημιουργία νέων χρηστών
        self.create_new_users()
        
        self.stdout.write(self.style.SUCCESS('Τα δεδομένα επαναφέρθηκαν επιτυχώς!'))

    def clean_all_data(self):
        """Καθαρισμός όλων των δεδομένων"""
        self.stdout.write('Διαγραφή ειδοποιήσεων...')
        Notification.objects.all().delete()
        
        self.stdout.write('Διαγραφή αιτήσεων αδειών...')
        LeaveRequest.objects.all().delete()
        
        self.stdout.write('Διαγραφή χρηστών (εκτός από superusers)...')
        User.objects.filter(is_superuser=False).delete()
        
        self.stdout.write(self.style.SUCCESS('Καθαρισμός ολοκληρώθηκε!'))

    def create_new_users(self):
        """Δημιουργία νέων dummy users"""
        self.stdout.write('Δημιουργία νέων χρηστών...')
        
        # Βρίσκω τα τμήματα Γ και Δ
        try:
            tmima_c = Department.objects.get(code='TMIMA_C')
            tmima_d = Department.objects.get(code='TMIMA_D')
        except Department.DoesNotExist:
            self.stdout.write(self.style.ERROR('Τα τμήματα Γ και Δ δεν βρέθηκαν. Εκτελέστε πρώτα create_dummy_data.'))
            return

        # Χρήστες προς δημιουργία
        users_data = [
            {
                'username': 'apettas',
                'first_name': 'Ανδρέας',
                'last_name': 'Πέττας',
                'email': 'a.pettas@pdede.gov.gr',
                'employee_id': 'EMP001',
                'department': tmima_d,
                'role': 'department_manager',
                'password': '123'
            },
            {
                'username': 'tolia',
                'first_name': 'Κορίνα',
                'last_name': 'Τόλια',
                'email': 'k.tolia@pdede.gov.gr',
                'employee_id': 'EMP002',
                'department': tmima_c,
                'role': 'department_manager',
                'password': '123'
            },
            {
                'username': 'korsianou',
                'first_name': 'Κατερίνα',
                'last_name': 'Κορσιάνου',
                'email': 'k.korsianou@pdede.gov.gr',
                'employee_id': 'EMP003',
                'department': tmima_c,
                'role': 'employee',
                'password': '123'
            },
            {
                'username': 'fotopoulou',
                'first_name': 'Βάσω',
                'last_name': 'Φωτοπούλου',
                'email': 'v.fotopoulou@pdede.gov.gr',
                'employee_id': 'EMP004',
                'department': tmima_c,
                'role': 'employee',
                'password': '123'
            },
            {
                'username': 'kizilou',
                'first_name': 'Όλγα',
                'last_name': 'Κυζίλου',
                'email': 'o.kizilou@pdede.gov.gr',
                'employee_id': 'EMP005',
                'department': tmima_c,
                'role': 'employee',
                'password': '123'
            }
        ]

        # Ορισμός του manager για τους υπαλλήλους του Τμήματος Γ
        manager_tolia = None
        
        for user_data in users_data:
            user = User.objects.create_user(
                username=user_data['username'],
                email=user_data['email'],
                password=user_data['password'],
                first_name=user_data['first_name'],
                last_name=user_data['last_name'],
                employee_id=user_data['employee_id'],
                department=user_data['department'],
                role=user_data['role']
            )
            
            # Αποθήκευση της αναφοράς στον manager του Τμήματος Γ
            if user_data['username'] == 'tolia':
                manager_tolia = user
            
            self.stdout.write(f'Δημιουργήθηκε: {user.full_name} ({user.username}) - {user.get_role_display()}')

        # Ορισμός του manager για τους υπαλλήλους του Τμήματος Γ
        if manager_tolia:
            User.objects.filter(
                department=tmima_c,
                role='employee'
            ).update(manager=manager_tolia)
            self.stdout.write(f'Οι υπάλληλοι του Τμήματος Γ ορίστηκαν υπό την εποπτεία της {manager_tolia.full_name}')

        self.stdout.write(self.style.SUCCESS('Όλοι οι χρήστες δημιουργήθηκαν επιτυχώς!'))
        
        # Εμφάνιση σύνοψης
        self.stdout.write(self.style.SUCCESS('\n=== ΣΥΝΟΨΗ ΧΡΗΣΤΩΝ ==='))
        self.stdout.write(f'Προϊστάμενος Τμήματος Δ: apettas / 123 (Ανδρέας Πέττας)')
        self.stdout.write(f'Προϊστάμενος Τμήματος Γ: tolia / 123 (Κορίνα Τόλια)')
        self.stdout.write(f'Υπάλληλος Τμήματος Γ: korsianou / 123 (Κατερίνα Κορσιάνου)')
        self.stdout.write(f'Υπάλληλος Τμήματος Γ: fotopoulou / 123 (Βάσω Φωτοπούλου)')
        self.stdout.write(f'Υπάλληλος Τμήματος Γ: kizilou / 123 (Όλγα Κυζίλου)')