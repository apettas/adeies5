"""
Management command για ετήσιο rollover αδειών
Τρέχει κάθε 1η Ιανουαρίου (ή manual από admin)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User


class Command(BaseCommand):
    help = 'Ετήσιο rollover υπολοίπων αδειών. Τρέχει κάθε 1η Ιανουαρίου.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Εμφάνιση αλλαγών χωρίς αποθήκευση',
        )
        parser.add_argument(
            '--year',
            type=int,
            default=None,
            help='Έτος για rollover (default: current year)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        year = options['year'] or timezone.now().year

        self.stdout.write(self.style.SUCCESS(
            f'=== Rollover Αδειών για το {year} {"(DRY RUN)" if dry_run else ""} ==='
        ))

        active_users = User.objects.filter(is_active=True)
        updated_count = 0

        for user in active_users:
            old_carryover = user.carryover_leave_days
            old_current = user.current_year_leave_balance

            # Μεταφορά τρέχοντος υπολοίπου στο carryover
            new_carryover = max(0, user.current_year_leave_balance)

            # Νέες άδειες για το νέο έτος
            new_current = user.annual_leave_entitlement

            # Reset sick leave counters
            new_sick_days_current = 0
            new_sick_leave_with_declaration = 2

            if not dry_run:
                user.carryover_leave_days = new_carryover
                user.current_year_leave_balance = new_current
                user.sick_days_current_year = new_sick_days_current
                user.sick_leave_with_declaration = new_sick_leave_with_declaration
                user.leave_balance = user.calculate_total_leave_balance()
                user.save()

            self.stdout.write(
                f'  {user.email}: '
                f'carryover {old_carryover}→{new_carryover}, '
                f'current {old_current}→{new_current}, '
                f'sick_days reset'
            )
            updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nΟλοκληρώθηκε! Ενημερώθηκαν {updated_count} χρήστες.'
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Αυτό ήταν DRY RUN - δεν έγιναν αλλαγές.'
            ))
