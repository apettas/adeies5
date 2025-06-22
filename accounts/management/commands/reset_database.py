from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from io import StringIO


class Command(BaseCommand):
    help = 'Πλήρης επαναφορά βάσης δεδομένων (καθαρισμός δυναμικών + φόρτωση στατικών δεδομένων)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Πλήρης επαναφορά χωρίς ερώτηση επιβεβαίωσης',
        )
        parser.add_argument(
            '--keep-superuser',
            action='store_true',
            help='Διατήρηση του superuser κατά τον καθαρισμό χρηστών',
        )
        parser.add_argument(
            '--update-static',
            action='store_true',
            help='Αναγκαστική ενημέρωση στατικών δεδομένων (force update)',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING('=== ΠΛΗΡΗΣ ΕΠΑΝΑΦΟΡΑ ΒΑΣΗΣ ΔΕΔΟΜΕΝΩΝ ===')
        )
        
        # Επιβεβαίωση από χρήστη
        if not options['force']:
            self.stdout.write(
                self.style.ERROR('ΠΡΟΣΟΧΗ: Αυτή η ενέργεια θα διαγράψει ΟΛΕΣ τις αιτήσεις αδειών, '
                               'ειδοποιήσεις και χρήστες!')
            )
            self.stdout.write('Τα στατικά δεδομένα (τμήματα, ρόλοι, τύποι αδειών) θα επαναφορτωθούν.')
            
            confirmation = input('\nΕίστε σίγουροι ότι θέλετε να προχωρήσετε; (yes/no): ')
            if confirmation.lower() not in ['yes', 'y']:
                self.stdout.write('Η επαναφορά ακυρώθηκε.')
                return

        try:
            with transaction.atomic():
                # Βήμα 1: Καθαρισμός δυναμικών δεδομένων
                self.stdout.write(
                    self.style.HTTP_INFO('\n=== ΒΗΜΑ 1: Καθαρισμός δυναμικών δεδομένων ===')
                )
                
                # Καθαρισμός όλων των δυναμικών δεδομένων
                call_command('clear_dynamic_data', '--all', '--confirm', stdout=self.stdout)
                
                # Βήμα 2: Φόρτωση στατικών δεδομένων
                self.stdout.write(
                    self.style.HTTP_INFO('\n=== ΒΗΜΑ 2: Φόρτωση στατικών δεδομένων ===')
                )
                
                # Φόρτωση στατικών δεδομένων
                static_args = ['load_static_data']
                if options['update_static']:
                    static_args.append('--force')
                
                call_command(*static_args, stdout=self.stdout)
                
                # Βήμα 3: Δημιουργία αρχικού superuser αν δεν υπάρχει
                self.stdout.write(
                    self.style.HTTP_INFO('\n=== ΒΗΜΑ 3: Έλεγχος superuser ===')
                )
                
                self.ensure_superuser()

            self.stdout.write(
                self.style.SUCCESS('\n=== ΕΠΙΤΥΧΗΣ ΕΠΑΝΑΦΟΡΑ ΒΑΣΗΣ ΔΕΔΟΜΕΝΩΝ ===')
            )
            self.stdout.write('Η βάση δεδομένων επαναφέρθηκε επιτυχώς!')
            self.stdout.write('Στοιχεία σύνδεσης superuser:')
            self.stdout.write('  Email: admin@pdede.gr')
            self.stdout.write('  Password: admin123')
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Σφάλμα κατά την επαναφορά: {str(e)}')
            )
            raise

    def ensure_superuser(self):
        """Δημιουργία αρχικού superuser αν δεν υπάρχει"""
        from django.contrib.auth import get_user_model
        
        User = get_user_model()
        superuser_email = 'admin@pdede.gr'
        
        if not User.objects.filter(email=superuser_email).exists():
            self.stdout.write('Δημιουργία αρχικού superuser...')
            
            # Φόρτωση των ρόλων
            from accounts.models import Role
            
            superuser = User.objects.create_superuser(
                email=superuser_email,
                password='admin123',
                first_name='Admin',
                last_name='ΠΔΕΔΕ',
                employee_id='ADMIN001'
            )
            
            # Ανάθεση όλων των ρόλων στον superuser (χωρίς διπλότυπα)
            all_roles = Role.objects.all()
            if all_roles.exists():
                superuser.roles.clear()  # Καθαρίζουμε πρώτα τους υπάρχοντες ρόλους
                superuser.roles.set(all_roles)
                self.stdout.write(f'  Ανατέθηκαν {all_roles.count()} ρόλοι στον superuser')
            
            self.stdout.write('  Δημιουργήθηκε superuser: admin@pdede.gr')
        else:
            self.stdout.write('  Ο superuser υπάρχει ήδη')

    def show_summary(self):
        """Εμφάνιση σύνοψης επαναφοράς"""
        from django.contrib.auth import get_user_model
        from accounts.models import Department, Role
        from leaves.models import LeaveType, LeaveRequest
        from notifications.models import Notification
        
        User = get_user_model()
        
        self.stdout.write(
            self.style.HTTP_INFO('\n=== ΣΥΝΟΨΗ ΒΑΣΗΣ ΔΕΔΟΜΕΝΩΝ ===')
        )
        
        # Στατικά δεδομένα
        self.stdout.write('Στατικά δεδομένα:')
        self.stdout.write(f'  Τμήματα: {Department.objects.count()}')
        self.stdout.write(f'  Ρόλοι: {Role.objects.count()}')
        self.stdout.write(f'  Τύποι αδειών: {LeaveType.objects.count()}')
        
        # Δυναμικά δεδομένα
        self.stdout.write('Δυναμικά δεδομένα:')
        self.stdout.write(f'  Χρήστες: {User.objects.count()}')
        self.stdout.write(f'  Αιτήσεις αδειών: {LeaveRequest.objects.count()}')
        self.stdout.write(f'  Ειδοποιήσεις: {Notification.objects.count()}')