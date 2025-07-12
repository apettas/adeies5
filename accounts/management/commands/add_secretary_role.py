from django.core.management.base import BaseCommand
from accounts.models import Role


class Command(BaseCommand):
    help = 'Προσθέτει τον ρόλο Secretary για τα τμήματα ΚΕΔΑΣΥ/ΚΕΠΕΑ'

    def handle(self, *args, **options):
        # Δημιουργία ρόλου Secretary αν δεν υπάρχει
        role, created = Role.objects.get_or_create(
            name='Secretary',
            defaults={
                'description': 'Γραμματέας - διαχείριση πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ',
                'is_active': True
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Δημιουργήθηκε ο ρόλος: {role.name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Ο ρόλος "{role.name}" υπάρχει ήδη')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Ο ρόλος Secretary είναι διαθέσιμος για χρήση στα ΚΕΔΑΣΥ/ΚΕΠΕΑ')
        )