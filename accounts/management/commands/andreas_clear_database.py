from django.core.management.base import BaseCommand
from django.db import transaction
from django.apps import apps
from django.contrib.auth import get_user_model


class Command(BaseCommand):
    help = 'Σβήνει όλα τα δεδομένα από τη βάση δεδομένων'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Επιβεβαιώνει τη διαγραφή χωρίς prompt',
        )

    def handle(self, *args, **options):
        if not options['confirm']:
            confirm = input(
                'ΠΡΟΣΟΧΗ: Αυτή η εντολή θα σβήσει ΟΛΑ τα δεδομένα από τη βάση δεδομένων!\n'
                'Είστε σίγουροι ότι θέλετε να συνεχίσετε; (yes/no): '
            )
            if confirm.lower() != 'yes':
                self.stdout.write(
                    self.style.WARNING('Η διαγραφή ακυρώθηκε.')
                )
                return

        self.stdout.write(
            self.style.WARNING('Ξεκινάει η διαγραφή όλων των δεδομένων...')
        )

        with transaction.atomic():
            # Παίρνουμε όλα τα models από όλες τις εφαρμογές
            all_models = apps.get_models()
            
            # Διαγραφή δεδομένων από κάθε model
            for model in all_models:
                try:
                    count = model.objects.count()
                    if count > 0:
                        model.objects.all().delete()
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Διαγράφηκαν {count} εγγραφές από {model._meta.label}'
                            )
                        )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'Σφάλμα κατά τη διαγραφή από {model._meta.label}: {str(e)}'
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS('Η διαγραφή όλων των δεδομένων ολοκληρώθηκε επιτυχώς!')
        )
        self.stdout.write(
            self.style.WARNING(
                'Για να επαναφέρετε τα static data, εκτελέστε: python manage.py andreas_static_data'
            )
        )
        self.stdout.write(
            self.style.WARNING(
                'Για να δημιουργήσετε νέο superuser, εκτελέστε: python manage.py andreas_superuser'
            )
        )