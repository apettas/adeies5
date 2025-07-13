from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
import logging

User = get_user_model()

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Επαναφορά ετήσιων υπολοίπων αδειών για όλους τους χρήστες'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Προσομοίωση εκτέλεσης χωρίς αποθήκευση αλλαγών',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='Επαναφορά μόνο για συγκεκριμένο χρήστη (για testing)',
        )
        parser.add_argument(
            '--year',
            type=int,
            default=timezone.now().year,
            help='Έτος για το οποίο γίνεται η επαναφορά (default: τρέχον έτος)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        user_id = options['user_id']
        year = options['year']
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔄 DRY RUN MODE - Δεν θα γίνουν αλλαγές στη βάση δεδομένων')
            )
        
        self.stdout.write(
            self.style.SUCCESS(f'📅 Επαναφορά ετήσιων υπολοίπων αδειών για το έτος {year}')
        )
        
        # Φιλτράρισμα χρηστών
        if user_id:
            users = User.objects.filter(id=user_id)
            if not users.exists():
                self.stdout.write(
                    self.style.ERROR(f'❌ Δεν βρέθηκε χρήστης με ID {user_id}')
                )
                return
        else:
            users = User.objects.filter(is_active=True)
        
        total_users = users.count()
        self.stdout.write(f'👥 Θα επεξεργαστούν {total_users} χρήστες')
        
        updated_count = 0
        error_count = 0
        
        with transaction.atomic():
            for user in users:
                try:
                    # Υπολογισμός προηγούμενων υπολοίπων
                    old_carryover = user.carryover_leave_days
                    old_current_year = user.current_year_leave_balance
                    old_total = user.leave_balance
                    
                    if not dry_run:
                        # Επαναφορά υπολοίπων
                        user.reset_yearly_leave_balance()
                        updated_count += 1
                    
                    # Υπολογισμός νέων υπολοίπων
                    new_carryover = old_current_year if not dry_run else old_current_year
                    new_current_year = user.annual_leave_entitlement
                    new_total = new_carryover + new_current_year
                    
                    self.stdout.write(
                        f'✅ {user.full_name} (ID: {user.id})'
                    )
                    self.stdout.write(
                        f'   📊 Προηγούμενα υπόλοιπα: {old_carryover} μεταφερόμενες + {old_current_year} τρέχοντος = {old_total} σύνολο'
                    )
                    self.stdout.write(
                        f'   🔄 Νέα υπόλοιπα: {new_carryover} μεταφερόμενες + {new_current_year} τρέχοντος = {new_total} σύνολο'
                    )
                    
                    if new_total != old_total:
                        change = new_total - old_total
                        change_icon = '📈' if change > 0 else '📉'
                        self.stdout.write(
                            f'   {change_icon} Αλλαγή: {change:+} ημέρες'
                        )
                    
                    self.stdout.write('')  # Κενή γραμμή
                    
                except Exception as e:
                    error_count += 1
                    self.stdout.write(
                        self.style.ERROR(f'❌ Σφάλμα για χρήστη {user.full_name} (ID: {user.id}): {e}')
                    )
                    logger.error(f'Error resetting leave balance for user {user.id}: {e}')
        
        # Σύνοψη αποτελεσμάτων
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('📋 ΣΥΝΟΨΗ ΑΠΟΤΕΛΕΣΜΑΤΩΝ'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        
        if dry_run:
            self.stdout.write(f'🔄 Dry run mode: Θα επεξεργάζονταν {total_users} χρήστες')
        else:
            self.stdout.write(f'✅ Επιτυχής επεξεργασία: {updated_count} χρήστες')
        
        if error_count > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ Σφάλματα: {error_count} χρήστες')
            )
        
        self.stdout.write(f'👥 Σύνολο χρηστών: {total_users}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('⚠️  Για να εκτελεστεί η επαναφορά, τρέξτε το command χωρίς --dry-run')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'🎉 Η επαναφορά ετήσιων υπολοίπων αδειών για το έτος {year} ολοκληρώθηκε επιτυχώς!')
            )
        
        # Συμβουλές για automation
        if not dry_run and not user_id:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('💡 ΣΥΜΒΟΥΛΕΣ ΓΙΑ AUTOMATION:'))
            self.stdout.write('   • Για αυτοματοποίηση, προσθέστε στο crontab:')
            self.stdout.write('   • 0 0 1 1 * /path/to/python manage.py reset_yearly_leave_balances')
            self.stdout.write('   • Αυτό θα τρέχει κάθε 1η Ιανουαρίου στις 00:00')
            self.stdout.write('')
            self.stdout.write('   • Για testing πρώτα:')
            self.stdout.write('   • python manage.py reset_yearly_leave_balances --dry-run')
            self.stdout.write('')
            self.stdout.write('   • Για συγκεκριμένο χρήστη:')
            self.stdout.write('   • python manage.py reset_yearly_leave_balances --user-id 123')