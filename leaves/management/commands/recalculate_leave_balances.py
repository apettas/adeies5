"""
Management command για επαναϋπολογισμό υπολοίπων αδειών
Διορθώνει χρήστες των οποίων τα υπόλοιπα δεν ενημερώθηκαν σωστά
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import User
from leaves.models import LeaveRequest


class Command(BaseCommand):
    help = 'Επαναϋπολογισμός υπολοίπων αδειών για όλους τους χρήστες'

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
            f'=== Επαναϋπολογισμός Υπολοίπων Αδειών {"(DRY RUN)" if dry_run else ""} ==='
        ))

        # Βρες όλους τους χρήστες
        users = User.objects.filter(is_active=True)
        if email:
            users = users.filter(email=email)

        fixed_count = 0

        for user in users:
            # Βρες όλες τις ολοκληρωμένες αιτήσεις που μετράνε στο υπόλοιπο
            completed_leaves = LeaveRequest.objects.filter(
                user=user,
                status='COMPLETED',
                leave_type__affects_regular_leave_balance=True
            )

            total_used = sum(lr.total_days for lr in completed_leaves)

            # Υπολόγισε το σωστό υπόλοιπο
            correct_balance = user.annual_leave_entitlement - total_used

            # Προσθήκη carryover αν υπάρχει
            correct_total = correct_balance + user.carryover_leave_days

            # Έλεγχος αν χρειάζεται διόρθωση
            if user.leave_balance != correct_total or user.current_year_leave_balance != correct_balance:
                old_balance = user.leave_balance
                old_current = user.current_year_leave_balance

                if not dry_run:
                    user.current_year_leave_balance = correct_balance
                    user.leave_balance = correct_total
                    user.save()

                self.stdout.write(
                    f'  {user.get_full_name()} ({user.email}): '
                    f'{old_balance}→{correct_total} (χρησιμοποίησε {total_used} ημέρες)'
                )
                fixed_count += 1
            else:
                self.stdout.write(
                    f'  {user.get_full_name()} ({user.email}): OK (υπόλοιπο={user.leave_balance})'
                )

        self.stdout.write(self.style.SUCCESS(
            f'\nΟλοκληρώθηκε! Διορθώθηκαν {fixed_count} χρήστες.'
        ))

        if dry_run:
            self.stdout.write(self.style.WARNING(
                'Αυτό ήταν DRY RUN - δεν έγιναν αλλαγές.'
            ))
