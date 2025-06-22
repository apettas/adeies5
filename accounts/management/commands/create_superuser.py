from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superuser for Django admin'

    def handle(self, *args, **options):
        # Έλεγχος αν υπάρχει ήδη superuser
        if User.objects.filter(is_superuser=True).exists():
            existing_superuser = User.objects.filter(is_superuser=True).first()
            self.stdout.write(
                self.style.SUCCESS(f'Superuser ήδη υπάρχει: {existing_superuser.username} ({existing_superuser.email})')
            )
            return

        try:
            # Δημιουργία νέου superuser
            superuser = User.objects.create_superuser(
                username='superadmin',
                email='superadmin@pdede.gov.gr',
                password='superadmin123',
                first_name='Super',
                last_name='Admin',
                employee_id='SUPER001'
            )
            self.stdout.write(
                self.style.SUCCESS(f'Superuser δημιουργήθηκε επιτυχώς: {superuser.username}')
            )
            self.stdout.write(
                self.style.SUCCESS(f'Username: {superuser.username}')
            )
            self.stdout.write(
                self.style.SUCCESS('Password: superadmin123')
            )
            self.stdout.write(
                self.style.SUCCESS(f'Email: {superuser.email}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Σφάλμα κατά τη δημιουργία superuser: {str(e)}')
            )