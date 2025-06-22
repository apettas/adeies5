from django.core.management.base import BaseCommand
from accounts.models import Role, User


class Command(BaseCommand):
    help = 'Δημιουργία βασικών ρόλων και migration παλιών δεδομένων'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Δημιουργία βασικών ρόλων...'))
        
        # Δημιουργία βασικών ρόλων
        self.create_roles()
        
        # Migration υπαρχόντων χρηστών (αν υπάρχουν)
        self.migrate_existing_users()
        
        self.stdout.write(self.style.SUCCESS('Setup ρόλων ολοκληρώθηκε επιτυχώς!'))

    def create_roles(self):
        """Δημιουργία βασικών ρόλων συστήματος"""
        roles_data = [
            {
                'code': 'employee',
                'name': 'Υπάλληλος',
                'description': 'Βασικός χρήστης που μπορεί να υποβάλλει αιτήσεις αδειών'
            },
            {
                'code': 'department_manager',
                'name': 'Προϊστάμενος Τμήματος',
                'description': 'Μπορεί να εγκρίνει/απορρίπτει αιτήσεις των υφισταμένων του'
            },
            {
                'code': 'leave_handler',
                'name': 'Χειριστής Αδειών',
                'description': 'Μπορεί να επεξεργάζεται όλες τις αιτήσεις αδειών'
            },
            {
                'code': 'administrator',
                'name': 'Διαχειριστής',
                'description': 'Πλήρη δικαιώματα διαχείρισης συστήματος'
            },
            {
                'code': 'hr_manager',
                'name': 'Διαχειριστής Ανθρώπινου Δυναμικού',
                'description': 'Διαχείριση προσωπικού και αναφορών'
            }
        ]

        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                code=role_data['code'],
                defaults={
                    'name': role_data['name'],
                    'description': role_data['description']
                }
            )
            
            if created:
                self.stdout.write(f'Δημιουργήθηκε ρόλος: {role.name}')
            else:
                self.stdout.write(f'Ρόλος υπάρχει ήδη: {role.name}')

    def migrate_existing_users(self):
        """Migration υπαρχόντων χρηστών από το παλιό σύστημα"""
        self.stdout.write('Migration υπαρχόντων χρηστών...')
        
        # Βρίσκω όλους τους χρήστες που δεν έχουν ρόλους
        users_without_roles = User.objects.filter(roles__isnull=True)
        
        for user in users_without_roles:
            # Προσδιορισμός ρόλου βάσει username ή τμήματος
            roles_to_assign = []
            
            # Βασικό: όλοι οι χρήστες είναι υπάλληλοι
            roles_to_assign.append('employee')
            
            # Έλεγχος για ειδικούς ρόλους βάσει username
            if user.username in ['tolia', 'apettas', 'kizilou']:
                roles_to_assign.append('department_manager')
            
            # Ανάθεση ρόλων
            for role_code in roles_to_assign:
                try:
                    role = Role.objects.get(code=role_code)
                    user.roles.add(role)
                    self.stdout.write(f'Προστέθηκε ρόλος "{role.name}" στον χρήστη {user.username}')
                except Role.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f'Ρόλος {role_code} δεν βρέθηκε για χρήστη {user.username}')
                    )

        self.stdout.write(self.style.SUCCESS('Migration χρηστών ολοκληρώθηκε!'))