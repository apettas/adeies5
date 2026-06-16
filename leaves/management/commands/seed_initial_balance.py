"""
Management command για δημιουργία αρχικών εγγραφών υπολοίπου
στο ledger (INITIAL_BALANCE) για όλους τους ενεργούς χρήστες.
"""
from django.core.management.base import BaseCommand
from accounts.models import User
from leaves.utils.balance_ledger import create_balance_entry, get_last_balance


class Command(BaseCommand):
    help = 'Δημιουργεί INITIAL_BALANCE εγγραφές στο ledger για όλους τους χρήστες'

    def add_arguments(self, parser):
        parser.add_argument(
            '--annual-entitlement',
            type=int,
            default=25,
            help='Ετήσιο δικαίωμα αδειών (default: 25)',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            default=None,
            help='Συγκεκριμένος χρήστης (προαιρετικό)',
        )

    def handle(self, *args, **options):
        annual = options['annual_entitlement']
        user_id = options['user_id']

        users = User.objects.filter(is_active=True)
        if user_id:
            users = users.filter(id=user_id)

        created = 0
        skipped = 0

        for user in users:
            if get_last_balance(user) is not None:
                self.stdout.write(f'  Υπάρχει ήδη υπόλοιπο για: {user.email}')
                skipped += 1
                continue

            user.annual_leave_entitlement = annual
            user.current_regular_leave_balance = annual
            user.save(update_fields=['annual_leave_entitlement', 'current_regular_leave_balance'])

            create_balance_entry(
                employee=user,
                entry_type='INITIAL_BALANCE',
                description=f'Αρχικό υπόλοιπο κανονικών αδειών ({annual} ημέρες)',
                balance_after=annual,
                days_delta=0,
                notes=f'Αρχική φόρτωση — {annual} ημέρες ετήσιου δικαιώματος',
                created_by=None,
            )
            created += 1
            self.stdout.write(self.style.SUCCESS(
                f'  Δημιουργήθηκε αρχικό υπόλοιπο για: {user.email} ({annual} ημέρες)'
            ))

        self.stdout.write(self.style.SUCCESS(
            f'\nΟλοκληρώθηκε! {created} νέες εγγραφές, {skipped} υπήρχαν ήδη.'
        ))