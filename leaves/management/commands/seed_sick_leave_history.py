"""
Εισαγωγή ιστορικών δεδομένων αναρρωτικών αδειών για έτη 2021-2025.

Χρήση: docker compose exec web python manage.py seed_sick_leave_history
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from accounts.models import User
from leaves.models import YearlySickLeaveTotal


HISTORICAL_DATA = {
    # email -> {year: days}
    'baladakis@sch.gr': {2021: 0, 2022: 0, 2023: 5, 2024: 8, 2025: 12},
    'kotsonis@sch.gr': {2021: 0, 2022: 10, 2023: 15, 2024: 3, 2025: 7},
    'karayan@sch.gr': {2021: 12, 2022: 8, 2023: 0, 2024: 0, 2025: 0},
    'apettas@sch.gr': {2021: 0, 2022: 0, 2023: 6, 2024: 0, 2025: 3},
    'tolia@sch.gr': {2021: 5, 2022: 3, 2023: 0, 2024: 12, 2025: 0},
    'korsianou@sch.gr': {2021: 0, 2022: 0, 2023: 0, 2024: 0, 2025: 0},
    'fotopoulou@sch.gr': {2021: 8, 2022: 4, 2023: 10, 2024: 2, 2025: 0},
    'sdeiagriniou@sch.gr': {2021: 0, 2022: 6, 2023: 12, 2024: 8, 2025: 15},
    'agorastou@sch.gr': {2021: 0, 2022: 0, 2023: 0, 2024: 0, 2025: 0},
    'xabesis@sch.gr': {2021: 0, 2022: 0, 2023: 3, 2024: 0, 2025: 8},
    'kizilou@sch.gr': {2021: 0, 2022: 0, 2023: 0, 2024: 0, 2025: 0},
    'delegkos@sch.gr': {2021: 0, 2022: 0, 2023: 0, 2024: 0, 2025: 0},
}


class Command(BaseCommand):
    help = 'Εισαγωγή ιστορικών δεδομένων αναρρωτικών αδειών 2021-2025'

    def handle(self, *args, **options):
        self.stdout.write('=== ΕΙΣΑΓΩΓΗ ΙΣΤΟΡΙΚΩΝ ΑΝΑΡΡΩΤΙΚΩΝ ===\n')

        YearlySickLeaveTotal.objects.all().delete()
        created = 0

        for email, years in HISTORICAL_DATA.items():
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                self.stdout.write(self.style.WARNING(f'  User not found: {email}'))
                continue

            for year, days in years.items():
                if days > 0:
                    YearlySickLeaveTotal.objects.create(
                        employee=user,
                        year=year,
                        total_days=days,
                        is_locked=True,
                        notes=f'Ιστορική καταχώρηση από data seed'
                    )
                    created += 1

            # Update total_sick_leave_last_5_years on user
            total = YearlySickLeaveTotal.objects.filter(
                employee=user, year__gte=2021, year__lte=2025
            ).aggregate(total=Sum('total_days'))['total'] or 0
            user.total_sick_leave_last_5_years = total
            user.save(update_fields=['total_sick_leave_last_5_years'])

        from django.db import models
        self.stdout.write(self.style.SUCCESS(f'Δημιουργήθηκαν {created} εγγραφές ιστορικού.'))
        self.stdout.write('  Τα πεδία total_sick_leave_last_5_years ενημερώθηκαν.')
