from django.core.management.base import BaseCommand
from accounts.models import Department, DepartmentType


class Command(BaseCommand):
    help = 'Ενημερώνει τον τύπο τμημάτων από έναν τύπο σε άλλον'
    
    def add_arguments(self, parser):
        parser.add_argument('from_type', type=str, help='Κωδικός παλιού τύπου τμήματος')
        parser.add_argument('to_type', type=str, help='Κωδικός νέου τύπου τμήματος')
        parser.add_argument('--dry-run', action='store_true', help='Προεπισκόπηση χωρίς εφαρμογή αλλαγών')
    
    def handle(self, *args, **options):
        from_type_code = options['from_type']
        to_type_code = options['to_type']
        dry_run = options['dry_run']
        
        try:
            # Βρίσκουμε τους τύπους τμημάτων
            from_type = DepartmentType.objects.get(code=from_type_code)
            to_type = DepartmentType.objects.get(code=to_type_code)
        except DepartmentType.DoesNotExist as e:
            self.stdout.write(
                self.style.ERROR(f'Δεν βρέθηκε τύπος τμήματος: {e}')
            )
            return
        
        # Βρίσκουμε τα τμήματα προς ενημέρωση
        departments = Department.objects.filter(department_type=from_type)
        
        if not departments.exists():
            self.stdout.write(
                self.style.WARNING(f'Δεν βρέθηκαν τμήματα με τύπο "{from_type.name}"')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f'Βρέθηκαν {departments.count()} τμήματα προς ενημέρωση:')
        )
        
        # Εμφάνιση λίστας τμημάτων
        for dept in departments:
            self.stdout.write(f'  • {dept.name} ({dept.code})')
        
        self.stdout.write(
            f'\nΑλλαγή από: "{from_type.name}" ({from_type.code})'
        )
        self.stdout.write(
            f'Αλλαγή σε: "{to_type.name}" ({to_type.code})'
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n🔍 ΠΡΟΕΠΙΣΚΟΠΗΣΗ - Καμία αλλαγή δεν θα εφαρμοστεί')
            )
            return
        
        # Εφαρμογή αλλαγών
        updated_count = departments.update(department_type=to_type)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Ενημερώθηκαν επιτυχώς {updated_count} τμήματα!\n'
                f'Όλα τα τμήματα που είχαν τύπο "{from_type.name}" '
                f'έχουν πλέον τύπο "{to_type.name}".'
            )
        )