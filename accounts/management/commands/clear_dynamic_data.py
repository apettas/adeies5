from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from leaves.models import LeaveRequest
from notifications.models import Notification
from django.db import transaction


User = get_user_model()


class Command(BaseCommand):
    help = 'Καθαρισμός δυναμικών δεδομένων (Users, Αιτήσεις αδειών, Notifications)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            action='store_true',
            help='Καθαρισμός χρηστών',
        )
        parser.add_argument(
            '--leave-requests',
            action='store_true',
            help='Καθαρισμός αιτήσεων αδειών',
        )
        parser.add_argument(
            '--notifications',
            action='store_true',
            help='Καθαρισμός ειδοποιήσεων',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Καθαρισμός όλων των δυναμικών δεδομένων',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Επιβεβαίωση καθαρισμού χωρίς ερώτηση',
        )

    def handle(self, *args, **options):
        if not any([options['users'], options['leave_requests'], 
                   options['notifications'], options['all']]):
            self.stdout.write(
                self.style.ERROR('Παρακαλώ επιλέξτε τι θέλετε να καθαρίσετε με τις παραμέτρους --users, --leave-requests, --notifications ή --all')
            )
            return

        # Επιβεβαίωση από χρήστη
        if not options['confirm']:
            confirmation = input('Είστε σίγουροι ότι θέλετε να προχωρήσετε; (yes/no): ')
            if confirmation.lower() not in ['yes', 'y']:
                self.stdout.write('Ακυρώθηκε.')
                return

        self.stdout.write(self.style.WARNING('Καθαρισμός δυναμικών δεδομένων...'))

        with transaction.atomic():
            if options['all'] or options['notifications']:
                self.clear_notifications()
            
            if options['all'] or options['leave_requests']:
                self.clear_leave_requests()
            
            if options['all'] or options['users']:
                self.clear_users()

        self.stdout.write(self.style.SUCCESS('Καθαρισμός ολοκληρώθηκε!'))

    def clear_notifications(self):
        """Καθαρισμός όλων των ειδοποιήσεων"""
        self.stdout.write('Καθαρισμός ειδοποιήσεων...')
        
        count = Notification.objects.count()
        if count > 0:
            Notification.objects.all().delete()
            self.stdout.write(f'  Διαγράφηκαν {count} ειδοποιήσεις')
        else:
            self.stdout.write('  Δεν βρέθηκαν ειδοποιήσεις για διαγραφή')

    def clear_leave_requests(self):
        """Καθαρισμός όλων των αιτήσεων αδειών"""
        self.stdout.write('Καθαρισμός αιτήσεων αδειών...')
        
        count = LeaveRequest.objects.count()
        if count > 0:
            LeaveRequest.objects.all().delete()
            self.stdout.write(f'  Διαγράφηκαν {count} αιτήσεις αδειών')
        else:
            self.stdout.write('  Δεν βρέθηκαν αιτήσεις αδειών για διαγραφή')

    def clear_users(self):
        """Καθαρισμός όλων των χρηστών"""
        self.stdout.write('Καθαρισμός χρηστών...')
        
        # Διατηρώ τον αρχικό superuser αν υπάρχει
        superuser_email = 'admin@pdede.gr'
        preserve_superuser = User.objects.filter(
            email=superuser_email, 
            is_superuser=True
        ).exists()
        
        if preserve_superuser:
            count = User.objects.exclude(email=superuser_email).count()
            if count > 0:
                User.objects.exclude(email=superuser_email).delete()
                self.stdout.write(f'  Διαγράφηκαν {count} χρήστες (διατηρήθηκε ο superuser)')
            else:
                self.stdout.write('  Δεν βρέθηκαν χρήστες για διαγραφή (εκτός από superuser)')
        else:
            count = User.objects.count()
            if count > 0:
                User.objects.all().delete()
                self.stdout.write(f'  Διαγράφηκαν {count} χρήστες')
            else:
                self.stdout.write('  Δεν βρέθηκαν χρήστες για διαγραφή')

    def handle_user_confirmation(self):
        """Επιβεβαίωση από χρήστη"""
        self.stdout.write(
            self.style.WARNING('ΠΡΟΣΟΧΗ: Αυτή η ενέργεια θα διαγράψει μόνιμα δεδομένα!')
        )
        
        confirmation = input('Είστε σίγουροι ότι θέλετε να προχωρήσετε; (yes/no): ')
        return confirmation.lower() in ['yes', 'y']