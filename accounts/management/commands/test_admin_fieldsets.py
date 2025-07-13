from django.core.management.base import BaseCommand
from accounts.admin import CustomUserAdmin
from accounts.models import User


class Command(BaseCommand):
    help = 'Test admin fieldsets για τα νέα πεδία κατάστασης αδειών'

    def handle(self, *args, **options):
        # Δημιουργία admin instance
        admin = CustomUserAdmin(User, None)

        self.stdout.write("Admin fieldsets:")
        for name, options in admin.fieldsets:
            self.stdout.write(f"  - {name}: {options.get('fields', [])}")

        self.stdout.write("\nAdmin add_fieldsets:")
        for name, options in admin.add_fieldsets:
            self.stdout.write(f"  - {name}: {options.get('fields', [])}")

        # Έλεγχος αν η ενότητα "Κατάσταση Αδειών" υπάρχει
        leave_status_found = False
        for name, options in admin.fieldsets:
            if name == "Κατάσταση Αδειών":
                leave_status_found = True
                fields = options.get('fields', [])
                self.stdout.write(
                    self.style.SUCCESS(f"\n✅ Η ενότητα 'Κατάσταση Αδειών' βρέθηκε με πεδία: {fields}")
                )
                
                # Έλεγχος αν όλα τα απαιτούμενα πεδία υπάρχουν
                required_fields = [
                    'annual_leave_entitlement',
                    'carryover_leave_days', 
                    'current_year_leave_balance',
                    'sick_leave_with_declaration',
                    'total_sick_leave_last_5_years'
                ]
                
                for field in required_fields:
                    if field in fields:
                        self.stdout.write(self.style.SUCCESS(f"  ✅ {field}"))
                    else:
                        self.stdout.write(self.style.ERROR(f"  ❌ {field} - MISSING"))
                break

        if not leave_status_found:
            self.stdout.write(
                self.style.ERROR("\n❌ Η ενότητα 'Κατάσταση Αδειών' δεν βρέθηκε!")
            )