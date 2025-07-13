from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction


class Command(BaseCommand):
    help = 'Δημιουργεί τον superuser για το σύστημα'

    def handle(self, *args, **options):
        User = get_user_model()
        
        email = 'pdede@sch.gr'
        password = 'admin123'
        first_name = 'Super'
        last_name = 'Admin'
        
        with transaction.atomic():
            # Έλεγχος αν υπάρχει ήδη ο χρήστης
            if User.objects.filter(email=email).exists():
                self.stdout.write(
                    self.style.WARNING(f'Ο χρήστης {email} υπάρχει ήδη')
                )
                return
            
            # Δημιουργία του superuser
            user = User.objects.create_superuser(
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'Ο superuser {email} δημιουργήθηκε επιτυχώς')
            )
            self.stdout.write(
                self.style.SUCCESS(f'Email: {email}')
            )
            self.stdout.write(
                self.style.SUCCESS(f'Password: {password}')
            )
            self.stdout.write(
                self.style.SUCCESS(f'Όνομα: {first_name} {last_name}')
            )