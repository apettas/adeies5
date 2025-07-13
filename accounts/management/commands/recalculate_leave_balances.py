from django.core.management.base import BaseCommand
from django.db.models import Q
from accounts.models import User
from leaves.models import LeaveRequest
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Επαναϋπολογίζει τα υπόλοιπα αδειών από την αρχή για όλους τους χρήστες'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Εκτελεί το command χωρίς να κάνει αλλαγές (preview μόνο)',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Διορθώνει μόνο έναν συγκεκριμένο χρήστη (όνομα ή ID)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        user_filter = options['user']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('*** DRY RUN MODE - Δεν θα γίνουν αλλαγές ***'))
        
        # Επιλογή χρηστών
        if user_filter:
            try:
                # Δοκιμάζω πρώτα ως ID
                if user_filter.isdigit():
                    users = User.objects.filter(id=int(user_filter))
                else:
                    # Αναζήτηση με όνομα
                    users = User.objects.filter(
                        Q(first_name__icontains=user_filter) | 
                        Q(last_name__icontains=user_filter)
                    )
                
                if not users.exists():
                    self.stdout.write(self.style.ERROR(f'Δεν βρέθηκε χρήστης με κριτήριο: {user_filter}'))
                    return
                    
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Σφάλμα στην αναζήτηση χρήστη: {str(e)}'))
                return
        else:
            users = User.objects.all()
        
        self.stdout.write(f'Θα επεξεργαστούν {users.count()} χρήστες')
        
        fixed_count = 0
        total_difference = 0
        
        for user in users:
            # Υπολογίζω το σωστό υπόλοιπο
            completed_regular_requests = LeaveRequest.objects.filter(
                user=user,
                status='COMPLETED',
                leave_type__name='1 Κανονική Άδεια'
            )
            
            total_days_used = sum(req.total_days for req in completed_regular_requests)
            
            # Υπολογίζω το σωστό υπόλοιπο
            # Αρχικό υπόλοιπο: current_year_leave_balance + carryover_leave_days
            initial_balance = user.current_year_leave_balance + user.carryover_leave_days
            correct_balance = initial_balance - total_days_used
            
            current_balance = user.leave_balance
            
            self.stdout.write(f'Χρήστης: {user.full_name}')
            self.stdout.write(f'  Αρχικό υπόλοιπο: {initial_balance} ({user.current_year_leave_balance} + {user.carryover_leave_days})')
            self.stdout.write(f'  Χρησιμοποιημένες ημέρες: {total_days_used}')
            self.stdout.write(f'  Σωστό υπόλοιπο: {correct_balance}')
            self.stdout.write(f'  Τρέχον υπόλοιπο: {current_balance}')
            
            if current_balance != correct_balance:
                difference = correct_balance - current_balance
                self.stdout.write(f'  Διαφορά: {difference}')
                
                if not dry_run:
                    user.leave_balance = correct_balance
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Διορθώθηκε: {current_balance} → {correct_balance}'))
                    fixed_count += 1
                    total_difference += abs(difference)
                else:
                    self.stdout.write(f'  [DRY RUN] Θα διορθωνόταν: {current_balance} → {correct_balance}')
            else:
                self.stdout.write(self.style.SUCCESS(f'  ✓ Σωστό υπόλοιπο'))
            
            self.stdout.write('---')
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Διορθώθηκαν {fixed_count} χρήστες'))
            self.stdout.write(self.style.SUCCESS(f'Συνολική διαφορά: {total_difference} ημέρες'))
        else:
            self.stdout.write(self.style.WARNING('DRY RUN ολοκληρώθηκε - Δεν έγιναν αλλαγές'))