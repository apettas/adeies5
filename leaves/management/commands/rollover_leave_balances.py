"""
Management command για ετήσιο rollover αδειών μέσω ledger.

Δημιουργεί εγγραφές CARRYOVER_IMPORT στο ιστορικό υπολοίπου,
αντί να κάνει απευθείας μεταβολή των πεδίων.

Ο χειριστής πρέπει να τρέξει το command MANUALLY (όχι αυτόματα).
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from accounts.models import User
from leaves.utils.balance_ledger import create_balance_entry, get_last_balance


class Command(BaseCommand):
    help = 'Ετήσιο rollover υπολοίπων: δημιουργεί CARRYOVER_IMPORT εγγραφές στο ledger'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Εμφάνιση αλλαγών χωρίς αποθήκευση',
        )
        parser.add_argument(
            '--carryover-days',
            type=int,
            default=None,
            help='Πόσες ημέρες μεταφέρονται (default: όλο το τρέχον υπόλοιπο)',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            default=None,
            help='Συγκεκριμένος χρήστης (προαιρετικό)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        carryover_days = options['carryover_days']
        user_id = options['user_id']
        year = timezone.now().year

        self.stdout.write(self.style.SUCCESS(
            f'=== Rollover Αδειών για {year} — Δημιουργία CARRYOVER_IMPORT {"(DRY RUN)" if dry_run else ""} ==='
        ))

        users = User.objects.filter(is_active=True)
        if user_id:
            users = users.filter(id=user_id)

        if not users.exists():
            self.stdout.write(self.style.WARNING('Δεν βρέθηκαν χρήστες.'))
            return

        updated_count = 0

        for user in users:
            current_balance = get_last_balance(user)
            if current_balance is None:
                current_balance = user.current_regular_leave_balance

            amount = carryover_days if carryover_days is not None else current_balance
            amount = max(0, amount)

            self.stdout.write(
                f'  {user.email} ({user.full_name}): '
                f'τρέχον υπόλοιπο={current_balance}, '
                f'προς μεταφορά={amount}'
            )

            if not dry_run:
                if amount > 0:
                    create_balance_entry(
                        employee=user,
                        entry_type='CARRYOVER_IMPORT',
                        description=f'Μεταφορά υπολοίπου από προηγούμενο έτος στο {year}',
                        balance_after=amount,
                        days_delta=0,
                        notes=f'Αυτόματη εγγραφή carryover από command rollover_leave_balances',
                        created_by=None,
                    )

                user.annual_leave_entitlement = user.annual_leave_entitlement or 25
                user.save(update_fields=['annual_leave_entitlement'])

                updated_count += 1

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f'\nDRY RUN — Δεν έγιναν αλλαγές. Θα επηρεάζονταν {users.count()} χρήστες.'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nΟλοκληρώθηκε! Δημιουργήθηκαν εγγραφές carryover για {updated_count} χρήστες.'
            ))
            self.stdout.write(self.style.WARNING(
                'ΣΗΜΑΝΤΙΚΟ: Το carryover καταγράφηκε στο ledger. '
                'Χρησιμοποιήστε τη φόρμα "Μεταφορά Υπολοίπου" (CARRYOVER_IMPORT) '
                'στο web interface για μεμονωμένες διορθώσεις.'
            ))