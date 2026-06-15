from django.core.management.base import BaseCommand
from accounts.models import Specialty


class Command(BaseCommand):
    help = 'Εισαγωγή ειδικοτήτων από το αρχείο eidikot1.csv'

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv-path',
            default='/app/adeies5/eidikot1.csv',
            help='Διαδρομή στο αρχείο CSV (π.χ. /app/adeies5/eidikot1.csv ή /path/to/eidikot1.csv)',
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']

        with open(csv_path, encoding='utf-8') as f:
            lines = f.readlines()

        if not lines:
            self.stdout.write(self.style.WARNING('Το αρχείο CSV είναι άδειο.'))
            return

        header_skipped = False
        created_count = 0
        skipped_count = 0

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if not header_skipped:
                header_skipped = True
                continue

            parts = line.split(';')
            if len(parts) < 2:
                continue

            code = parts[0].strip()
            name = parts[1].strip()

            if not code or not name:
                continue

            specialty, created = Specialty.objects.get_or_create(
                specialties_full=name,
                defaults={'specialties_short': code, 'is_active': True},
            )

            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {code} - {name}')
                created_count += 1
            else:
                self.stdout.write(f'  ⚠️ Υπάρχει ήδη: {code} - {specialty.specialties_full}')
                skipped_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nΟλοκληρώθηκε! Δημιουργήθηκαν {created_count}, παραβλέφθηκαν {skipped_count}.'
        ))
