from django.core.management.base import BaseCommand
from accounts.models import Role


class Command(BaseCommand):
    help = 'Εμφανίζει όλους τους ρόλους στη βάση δεδομένων'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== Ρόλοι στη βάση δεδομένων ==='))
        
        roles = Role.objects.all().order_by('id')
        
        if not roles.exists():
            self.stdout.write(self.style.WARNING('Δεν βρέθηκαν ρόλοι στη βάση δεδομένων'))
            return
        
        for role in roles:
            self.stdout.write(f'ID: {role.id}')
            self.stdout.write(f'Code: {role.code}')
            self.stdout.write(f'Name: {role.name}')
            self.stdout.write(f'Description: {role.description}')
            self.stdout.write(f'Is Active: {role.is_active}')
            self.stdout.write('---')
        
        self.stdout.write(self.style.SUCCESS(f'Συνολικά βρέθηκαν {roles.count()} ρόλοι'))