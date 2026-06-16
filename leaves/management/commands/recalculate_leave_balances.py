"""
Management command για επαναϋπολογισμό υπολοίπων αδειών από το ledger.
Διορθώνει το cache current_regular_leave_balance όταν αποκλίνει από τις εγγραφές.
"""
from django.core.management.base import BaseCommand
from accounts.models import User
from leaves.utils.balance_ledger import create_balance_entry, get_last_balance


class Command(BaseCommand):
    help = 'Επαναϋπολογισμός cached υπολοίπων αδειών από το ledger'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Εμφάνιση αλλαγών χωρίς αποθήκευση',
        )
        parser.add_argument(
            '--email',
            type=str,
            default=None,
            help='Email συγκεκριμένου χρήστη (προαιρετικό)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        email = options['email']

        self.stdout.write(self.style.SUCCESS(
            f'=== Επαναϋπολογισμός Υπολοίπων (Ledger) {"(DRY RUN)" if dry_run else ""} ==='
        ))

        users = User.objects.filter(is_active=True)
        if email:
            users = users.filter(email=email)

        fixed_count = 0

        for user in users:
            ledger_balance = get_last_balance(user)
            if ledger_balance is None:
                ledger_balance = user.current_regular_leave_balance

            if user.current_regular_leave_balance != ledger_balance:
                old_balance = user.current_regular_leave_balance
                if not dry_run:
                    user.current_regular_leave_balance = ledger_balance
                    user.save(update_fields=['current_regular_leave_balance'])
                self.stdout.write(
                    f'  {user.get_full_name()} ({user.email}): '
                    f'cache {old_balance}→{ledger_balance}'
                )
                fixed_count += 1
            else:
                self.stdout.write(
                    f'  {user.get_full_name()} ({user.email}): OK (υπόλοιπο={ledger_balance})'
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nΟλοκληρώθηκε! Διορθώθηκαν {fixed_count} χρήστες.'
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Αυτό ήταν DRY RUN - δεν έγιναν αλλαγές.'
            ))
