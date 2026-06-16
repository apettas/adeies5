from django.core.management.base import BaseCommand
from accounts.models import Role, User
from accounts.role_constants import (
    ROLE_ADMIN,
    ROLE_EMPLOYEE,
    ROLE_HR_ADMIN,
    ROLE_LEAVE_HANDLER,
    ROLE_MANAGER,
)


class Command(BaseCommand):
    help = 'Δημιουργία canonical ρόλων και migration παλιών δεδομένων'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Δημιουργία βασικών ρόλων...'))
        self.create_roles()
        self.migrate_existing_users()
        self.stdout.write(self.style.SUCCESS('Setup ρόλων ολοκληρώθηκε επιτυχώς!'))

    def create_roles(self):
        """Δημιουργία canonical ρόλων συστήματος"""
        roles_data = [
            {
                'code': ROLE_EMPLOYEE,
                'name': 'Υπάλληλος',
                'description': 'Βασικός χρήστης που μπορεί να υποβάλλει αιτήσεις αδειών',
            },
            {
                'code': ROLE_MANAGER,
                'name': 'Προϊστάμενος Τμήματος',
                'description': 'Μπορεί να εγκρίνει/απορρίπτει αιτήσεις των υφισταμένων του',
            },
            {
                'code': ROLE_LEAVE_HANDLER,
                'name': 'Χειριστής Αδειών',
                'description': 'Μπορεί να επεξεργάζεται όλες τις αιτήσεις αδειών',
            },
            {
                'code': ROLE_ADMIN,
                'name': 'Διαχειριστής',
                'description': 'Πλήρη δικαιώματα διαχείρισης εφαρμογής αδειών',
            },
            {
                'code': ROLE_HR_ADMIN,
                'name': 'Διαχειριστής Ανθρώπινου Δυναμικού',
                'description': 'Διαχείριση προσωπικού και αναφορών',
            },
        ]

        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                code=role_data['code'],
                defaults={
                    'name': role_data['name'],
                    'description': role_data['description'],
                },
            )
            if created:
                self.stdout.write(f'Δημιουργήθηκε ρόλος: {role.name}')
            else:
                self.stdout.write(f'Ρόλος υπάρχει ήδη: {role.name}')

    def migrate_existing_users(self):
        """Ανάθεση EMPLOYEE σε χρήστες χωρίς ρόλους"""
        self.stdout.write('Migration υπαρχόντων χρηστών...')
        users_without_roles = User.objects.filter(roles__isnull=True).distinct()

        for user in users_without_roles:
            if user.add_role(ROLE_EMPLOYEE):
                self.stdout.write(f'Προστέθηκε ρόλος Υπάλληλος στον {user.email}')

        self.stdout.write(self.style.SUCCESS('Migration χρηστών ολοκληρώθηκε!'))
