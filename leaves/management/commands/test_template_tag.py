from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from leaves.models import LeaveRequest
from leaves.templatetags.leave_permissions import can_manager_approve

User = get_user_model()

class Command(BaseCommand):
    help = 'Test the custom template tag for KEDASY-SDEY approval logic'

    def handle(self, *args, **options):
        try:
            # Get KEDASY user
            kedasy_user = User.objects.get(email='kedasy@sch.gr')
            self.stdout.write(f"Found KEDASY user: {kedasy_user.full_name}")
            self.stdout.write(f"Department: {kedasy_user.department.name}")
            self.stdout.write(f"Department type: {kedasy_user.department.department_type.code}")
            
            # Get SDEU user
            sdeu_user = User.objects.get(email='sdei1@sch.gr')
            self.stdout.write(f"Found SDEU user: {sdeu_user.full_name}")
            self.stdout.write(f"Department: {sdeu_user.department.name}")
            self.stdout.write(f"Department type: {sdeu_user.department.department_type.code}")
            
            # Get a submitted leave request from SDEU user
            leave_request = LeaveRequest.objects.filter(
                user=sdeu_user,
                status='SUBMITTED'
            ).first()
            
            if leave_request:
                self.stdout.write(f"Found leave request: {leave_request.id}")
                
                # Test the template tag
                can_approve = can_manager_approve(kedasy_user, leave_request)
                self.stdout.write(f"Can KEDASY manager approve SDEU request: {can_approve}")
                
                # Test same department logic
                same_dept_request = LeaveRequest.objects.filter(
                    user__department=kedasy_user.department,
                    status='SUBMITTED'
                ).first()
                
                if same_dept_request:
                    can_approve_same = can_manager_approve(kedasy_user, same_dept_request)
                    self.stdout.write(f"Can KEDASY manager approve same department request: {can_approve_same}")
                
            else:
                self.stdout.write("No submitted leave request found for SDEU user")
                
        except User.DoesNotExist as e:
            self.stdout.write(f"User not found: {e}")
        except Exception as e:
            self.stdout.write(f"Error: {e}")