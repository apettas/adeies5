from django.core.management.base import BaseCommand
from leaves.models import LeaveRequest
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Διορθώνει τα υπόλοιπα αδειών για όλες τις ολοκληρωμένες αιτήσεις κανονικής άδειας'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Εκτελεί το command χωρίς να κάνει αλλαγές (preview μόνο)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('*** DRY RUN MODE - Δεν θα γίνουν αλλαγές ***'))
        
        # Βρίσκω όλες τις ολοκληρωμένες αιτήσεις κανονικής άδειας
        completed_requests = LeaveRequest.objects.filter(
            status='COMPLETED',
            leave_type__name='1 Κανονική Άδεια'
        ).select_related('user', 'leave_type').order_by('completed_at')
        
        self.stdout.write(f'Βρέθηκαν {completed_requests.count()} ολοκληρωμένες αιτήσεις κανονικής άδειας')
        
        fixed_count = 0
        total_days_fixed = 0
        
        for request in completed_requests:
            user = request.user
            
            # Αποθηκεύω το υπόλοιπο πριν
            balance_before = user.leave_balance
            
            self.stdout.write(f'Αίτηση ID: {request.id}')
            self.stdout.write(f'  Χρήστης: {user.full_name}')
            self.stdout.write(f'  Ημέρες: {request.total_days}')
            self.stdout.write(f'  Υπόλοιπο πριν: {balance_before}')
            
            if not dry_run:
                # Καλώ την _update_leave_balance_on_completion
                result = request._update_leave_balance_on_completion()
                
                # Ανανεώνω το user από τη βάση
                user.refresh_from_db()
                balance_after = user.leave_balance
                
                if balance_after != balance_before:
                    self.stdout.write(f'  Υπόλοιπο μετά: {balance_after}')
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Διορθώθηκε (-{balance_before - balance_after} ημέρες)'))
                    fixed_count += 1
                    total_days_fixed += (balance_before - balance_after)
                else:
                    self.stdout.write(f'  Υπόλοιπο μετά: {balance_after}')
                    self.stdout.write(self.style.WARNING(f'  - Δεν χρειαζόταν διόρθωση'))
            else:
                self.stdout.write(f'  [DRY RUN] Θα καλούσα _update_leave_balance_on_completion()')
            
            self.stdout.write('---')
        
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f'Διορθώθηκαν {fixed_count} αιτήσεις'))
            self.stdout.write(self.style.SUCCESS(f'Συνολικές ημέρες που αφαιρέθηκαν: {total_days_fixed}'))
        else:
            self.stdout.write(self.style.WARNING('DRY RUN ολοκληρώθηκε - Δεν έγιναν αλλαγές'))