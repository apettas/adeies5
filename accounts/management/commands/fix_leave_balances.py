from django.core.management.base import BaseCommand
from accounts.models import User
from leaves.models import LeaveRequest


class Command(BaseCommand):
    help = 'Διορθώνει τα υπόλοιπα αδειών για όλους τους χρήστες'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Διόρθωση υπολοίπων αδειών...'))
        
        users = User.objects.all()
        fixed_count = 0
        
        for user in users:
            # Υπολογισμός χρησιμοποιημένων ημερών από completed αιτήσεις
            completed_regular_requests = LeaveRequest.objects.filter(
                user=user,
                status='COMPLETED',
                leave_type__name='1 Κανονική Άδεια'
            )
            
            total_used_days = sum(req.total_days for req in completed_regular_requests)
            
            # Υπολογισμός αναμενόμενου υπολοίπου
            expected_balance = user.annual_leave_entitlement - total_used_days
            
            # Αν το τρέχον υπόλοιπο είναι διαφορετικό από το αναμενόμενο
            if user.current_year_leave_balance != expected_balance:
                old_balance = user.current_year_leave_balance
                
                # Διόρθωση υπολοίπου
                user.current_year_leave_balance = expected_balance
                user.leave_balance = user.calculate_total_leave_balance()
                user.save()
                
                self.stdout.write(
                    f'{user.full_name}: {old_balance} → {expected_balance} '
                    f'(Χρησιμοποιημένες: {total_used_days})'
                )
                fixed_count += 1
            else:
                self.stdout.write(f'{user.full_name}: OK ({user.current_year_leave_balance})')
        
        self.stdout.write(
            self.style.SUCCESS(f'Διορθώθηκαν {fixed_count} χρήστες από {users.count()} συνολικά')
        )