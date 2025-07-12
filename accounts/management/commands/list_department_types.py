from django.core.management.base import BaseCommand
from accounts.models import DepartmentType


class Command(BaseCommand):
    help = 'Εμφανίζει όλους τους τύπους τμημάτων'
    
    def add_arguments(self, parser):
        parser.add_argument('--active-only', action='store_true', help='Εμφάνιση μόνο ενεργών τύπων')
        parser.add_argument('--inactive-only', action='store_true', help='Εμφάνιση μόνο ανενεργών τύπων')
    
    def handle(self, *args, **options):
        queryset = DepartmentType.objects.all()
        
        # Φιλτράρισμα βάσει των επιλογών
        if options['active_only']:
            queryset = queryset.filter(is_active=True)
            title = "Ενεργοί Τύποι Τμημάτων"
        elif options['inactive_only']:
            queryset = queryset.filter(is_active=False)
            title = "Ανενεργοί Τύποι Τμημάτων"
        else:
            title = "Όλοι οι Τύποι Τμημάτων"
        
        if not queryset.exists():
            self.stdout.write(
                self.style.WARNING('Δεν βρέθηκαν τύποι τμημάτων!')
            )
            return
        
        self.stdout.write(
            self.style.SUCCESS(f"\n=== {title} ===\n")
        )
        
        for dept_type in queryset.order_by('name'):
            status = "✅ Ενεργός" if dept_type.is_active else "❌ Ανενεργός"
            departments_count = dept_type.departments.count()
            
            self.stdout.write(
                f"📋 {dept_type.name} ({dept_type.code})\n"
                f"   Κατάσταση: {status}\n"
                f"   Περιγραφή: {dept_type.description or 'Χωρίς περιγραφή'}\n"
                f"   Τμήματα που χρησιμοποιούν: {departments_count}\n"
                f"   Δημιουργήθηκε: {dept_type.created_at.strftime('%d/%m/%Y %H:%M')}\n"
            )
        
        self.stdout.write(
            self.style.SUCCESS(f"\nΣυνολικά: {queryset.count()} τύποι τμημάτων")
        )