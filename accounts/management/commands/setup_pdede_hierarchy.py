from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import DepartmentType, Department, Role


class Command(BaseCommand):
    help = 'Δημιουργία της ιεραρχικής δομής της ΠΔΕΔΕ'

    def handle(self, *args, **options):
        with transaction.atomic():
            self.stdout.write('Δημιουργία ιεραρχικής δομής ΠΔΕΔΕ...')
            
            # Δημιουργία τύπου τμήματος ΠΔΕΔΕ αν δεν υπάρχει
            pdede_type, created = DepartmentType.objects.get_or_create(
                code='PDEDE',
                defaults={
                    'name': 'Περιφερειακή Διεύθυνση Εκπαίδευσης Δυτικής Ελλάδας',
                    'description': 'Τμήματα της ΠΔΕΔΕ με ειδική ιεραρχική δομή έγκρισης αδειών',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'✓ Δημιουργήθηκε τύπος τμήματος: {pdede_type.name}')
            else:
                self.stdout.write(f'→ Υπάρχει ήδη τύπος τμήματος: {pdede_type.name}')
            
            # Δημιουργία τύπου τμήματος Αυτοτελής Διεύθυνση αν δεν υπάρχει
            autotelous_type, created = DepartmentType.objects.get_or_create(
                code='AUTOTELOUS',
                defaults={
                    'name': 'Αυτοτελής Διεύθυνση',
                    'description': 'Αυτοτελής Διεύθυνση της ΠΔΕΔΕ',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'✓ Δημιουργήθηκε τύπος τμήματος: {autotelous_type.name}')
            else:
                self.stdout.write(f'→ Υπάρχει ήδη τύπος τμήματος: {autotelous_type.name}')
            
            # Δημιουργία τύπου τμήματος για τα επιμέρους τμήματα
            tmima_type, created = DepartmentType.objects.get_or_create(
                code='TMIMA_PDEDE',
                defaults={
                    'name': 'Τμήμα ΠΔΕΔΕ',
                    'description': 'Τμήματα της ΠΔΕΔΕ (Α, Β, Γ, Δ, Νομική Υποστήριξη)',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'✓ Δημιουργήθηκε τύπος τμήματος: {tmima_type.name}')
            else:
                self.stdout.write(f'→ Υπάρχει ήδη τύπος τμήματος: {tmima_type.name}')
            
            self.stdout.write('\n=== Δομή Ιεραρχίας ΠΔΕΔΕ ===')
            self.stdout.write('1. ΠΔΕΔΕ (κορυφή)')
            self.stdout.write('2. Αυτοτελής Διεύθυνση')
            self.stdout.write('3. Τμήματα: Α, Β, Γ, Δ, Νομική Υποστήριξη')
            
            self.stdout.write('\n=== Λογική Έγκρισης ===')
            self.stdout.write('• Υπάλληλος τμήματος → εγκρίνει ο προϊστάμενος του τμήματος')
            self.stdout.write('• Προϊστάμενος τμήματος → εγκρίνει ο προϊστάμενος της Αυτοτελής Διεύθυνσης')
            self.stdout.write('• Προϊστάμενος Αυτοτελής Διεύθυνσης → εγκρίνει ο προϊστάμενος της ΠΔΕΔΕ')
            self.stdout.write('• Προϊστάμενος ΠΔΕΔΕ → ΔΕΝ μπορεί να αιτηθεί άδεια μέσω του συστήματος')
            
            self.stdout.write(
                self.style.SUCCESS('\n✓ Ολοκληρώθηκε η δημιουργία της ιεραρχικής δομής ΠΔΕΔΕ')
            )