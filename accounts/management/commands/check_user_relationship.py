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

            # Check for kotsonis@sch.gr
            employee = User.objects.get(email='kotsonis@sch.gr')
            self.stdout.write(f'Found employee: {employee.full_name} with roles: {", ".join([role.name for role in employee.roles.all()])}')
            self.stdout.write(f'Department: {employee.department.name if employee.department else "None"}')
            
            # Check if they are in the same department
            if supervisor.department and employee.department:
                self.stdout.write(f'Same department: {supervisor.department.id == employee.department.id}')
            else:
                self.stdout.write('Department comparison: Not possible (one or both have no department)')

        except User.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'User not found: {str(e)}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
