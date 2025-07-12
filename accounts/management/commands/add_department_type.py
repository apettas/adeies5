from django.core.management.base import BaseCommand
from accounts.models import DepartmentType


class Command(BaseCommand):
    help = 'Προσθέτει νέο τύπο τμήματος'
    
    def add_arguments(self, parser):
        parser.add_argument('code', type=str, help='Κωδικός τύπου τμήματος')
        parser.add_argument('name', type=str, help='Όνομα τύπου τμήματος')
        parser.add_argument('--description', type=str, default='', help='Περιγραφή τύπου τμήματος')
        parser.add_argument('--inactive', action='store_true', help='Δημιουργία ως ανενεργό')
    
    def handle(self, *args, **options):
        code = options['code']
        name = options['name']
        description = options['description']
        is_active = not options['inactive']
        
        # Έλεγχος αν υπάρχει ήδη
        if DepartmentType.objects.filter(code=code).exists():
            self.stdout.write(
                self.style.ERROR(f'Ο τύπος τμήματος με κωδικό "{code}" υπάρχει ήδη!')
            )
            return
        
        # Δημιουργία νέου τύπου
        dept_type = DepartmentType.objects.create(
            code=code,
            name=name,
            description=description,
            is_active=is_active
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Δημιουργήθηκε επιτυχώς ο τύπος τμήματος:\n'
                f'  Κωδικός: {dept_type.code}\n'
                f'  Όνομα: {dept_type.name}\n'
                f'  Περιγραφή: {dept_type.description}\n'
                f'  Ενεργός: {"Ναι" if dept_type.is_active else "Όχι"}'
            )
        )