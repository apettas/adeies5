from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

User = get_user_model()

class Command(BaseCommand):
    help = 'Check the relationship between users to debug permission issues'

    def handle(self, *args, **options):
        self.stdout.write(self.style.HTTP_INFO('=== CHECKING USER RELATIONSHIPS ==='))

        try:
            # Check for apettas@sch.gr
            supervisor = User.objects.get(email='apettas@sch.gr')
            self.stdout.write(f'Found supervisor: {supervisor.full_name} with roles: {", ".join([role.name for role in supervisor.roles.all()])}')
            self.stdout.write(f'Department: {supervisor.department.name if supervisor.department else "None"}')

            # Check subordinates of apettas@sch.gr
            subordinates = User.objects.filter(manager=supervisor)
            self.stdout.write(f'Subordinates of {supervisor.full_name}: {subordinates.count()}')
            for sub in subordinates:
                self.stdout.write(f' - {sub.full_name} ({sub.email})')

            # Check for kotsonis@sch.gr
            employee = User.objects.get(email='kotsonis@sch.gr')
            self.stdout.write(f'Found employee: {employee.full_name} with roles: {", ".join([role.name for role in employee.roles.all()])}')
            self.stdout.write(f'Department: {employee.department.name if employee.department else "None"}')
            self.stdout.write(f'Manager: {employee.manager.full_name if employee.manager else "None"}')

        except User.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'User not found: {str(e)}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
