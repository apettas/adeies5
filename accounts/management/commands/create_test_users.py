from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Role, Department

User = get_user_model()

class Command(BaseCommand):
    help = 'Create test users for the system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('=== ΔΗΜΙΟΥΡΓΙΑ ΔΟΚΙΜΑΣΤΙΚΩΝ ΧΡΗΣΤΩΝ ==='))

        # Βοηθητικά objects
        try:
            leave_handler_role = Role.objects.get(code='LEAVE_HANDLER')
            manager_role = Role.objects.get(code='MANAGER')
            employee_role = Role.objects.get(code='EMPLOYEE')

            dept_primary = Department.objects.get(name='Τμήμα Πρωτοβάθμιας Εκπαίδευσης')
            dept_secondary = Department.objects.get(name='Τμήμα Δευτεροβάθμιας Εκπαίδευσης')
            dept_autonomous = Department.objects.get(name='Αυτοτελής Διεύθυνση Εκπαίδευσης')
        except Role.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'Σφάλμα: Ρόλος δεν βρέθηκε - {str(e)}'))
            return
        except Department.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'Σφάλμα: Τμήμα δεν βρέθηκε - {str(e)}'))
            return

        # Δεδομένα χρηστών
        users_data = [
            {
                'email': 'apettas@sch.gr',
                'first_name': 'Ανδρέας',
                'last_name': 'Πέττας',
                'password': '123',
                'department': dept_secondary,  # ΤΜΗΜΑ Δ
                'gender': 'M',  # ΑΝΔΡΑΣ
                'roles': [manager_role, leave_handler_role]
            },
            {
                'email': 'tolia@sch.gr',
                'first_name': 'Κορίνα',
                'last_name': 'Τόλια',
                'password': '123',
                'department': dept_primary,  # ΤΜΗΜΑ Γ
                'gender': 'F',  # ΓΥΝΑΙΚΑ
                'roles': [manager_role, leave_handler_role]
            },
            {
                'email': 'korsianou@sch.gr',
                'first_name': 'Κατερίνα',
                'last_name': 'Κορσιάνου',
                'password': '123',
                'department': dept_primary,  # ΤΜΗΜΑ Γ
                'gender': 'F',  # ΓΥΝΑΙΚΑ
                'roles': [employee_role, leave_handler_role]
            },
            {
                'email': 'fotopoulou@sch.gr',
                'first_name': 'Βάσω',
                'last_name': 'Φωτοπούλου',
                'password': '123',
                'department': dept_primary,  # ΤΜΗΜΑ Γ
                'gender': 'F',  # ΓΥΝΑΙΚΑ
                'roles': [employee_role, leave_handler_role]
            },
            {
                'email': 'kizilou@sch.gr',
                'first_name': 'Όλγα',
                'last_name': 'Κυζίλου',
                'password': '123',
                'department': dept_autonomous,  # Αυτοτελής Διεύθυνση
                'gender': 'F',  # Τυχαία τιμή
                'roles': [manager_role]
            },
            {
                'email': 'kotsonis@sch.gr',
                'first_name': 'Ιωάννης',
                'last_name': 'Κοτσώνης',
                'password': '123',
                'department': dept_secondary,  # ΤΜΗΜΑ Δ
                'gender': 'M',  # ΑΝΔΡΑΣ
                'roles': [employee_role]
            },
            {
                'email': 'baladakis@sch.gr',
                'first_name': 'Βασίλειος',
                'last_name': 'Μπαλαδάκης',
                'password': '123',
                'department': dept_secondary,  # ΤΜΗΜΑ Δ
                'gender': 'M',  # ΑΝΔΡΑΣ
                'roles': [employee_role]
            },
            {
                'email': 'karayan@sch.gr',
                'first_name': 'Θεόδωρος',
                'last_name': 'Κάραγιαν',
                'password': '123',
                'department': dept_secondary,  # ΤΜΗΜΑ Δ
                'gender': 'M',  # ΑΝΔΡΑΣ
                'roles': [employee_role]
            }
        ]

        created_count = 0
        for user_data in users_data:
            try:
                user, created = User.objects.get_or_create(
                    email=user_data['email'],
                    defaults={
                        'first_name': user_data['first_name'],
                        'last_name': user_data['last_name'],
                        'department': user_data['department'],
                        'gender': user_data.get('gender', 'O'),  # Τυχαία τιμή αν δεν υπάρχει
                    }
                )
                if created:
                    user.set_password(user_data['password'])
                    user.save()
                    user.roles.set(user_data['roles'])
                    role_names = [role.name for role in user_data['roles']]
                    self.stdout.write(f'✅ {user.first_name} {user.last_name} - {user.email}')
                    self.stdout.write(f'   Τμήμα: {user.department.name}')
                    self.stdout.write(f'   Ρόλοι: {", ".join(role_names)}')
                    self.stdout.write('')
                    created_count += 1
                else:
                    self.stdout.write(f'⚠️ Ο χρήστης {user.email} υπάρχει ήδη')
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Σφάλμα κατά τη δημιουργία χρήστη {user_data["email"]}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'Δημιουργήθηκαν {created_count} νέοι χρήστες!'))
