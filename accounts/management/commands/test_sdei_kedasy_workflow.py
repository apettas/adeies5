from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User, Department, DepartmentType, Role
from leaves.models import LeaveRequest, LeaveType
from django.utils import timezone


class Command(BaseCommand):
    help = 'Τεστάρει τη λειτουργικότητα ΣΔΕΥ-ΚΕΔΑΣΥ'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Ξεκινά το τεστ της λειτουργικότητας ΣΔΕΥ-ΚΕΔΑΣΥ...'))
        
        try:
            self.test_sdei_kedasy_relationship()
            self.stdout.write(self.style.SUCCESS('✓ Όλα τα τεστ πέρασαν επιτυχώς!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Σφάλμα: {str(e)}'))
    
    def test_sdei_kedasy_relationship(self):
        """Τεστάρει τη σχέση ΣΔΕΥ-ΚΕΔΑΣΥ"""
        
        # Καθαρισμός υπαρχόντων δεδομένων test
        User.objects.filter(email__contains='test@example.com').delete()
        Department.objects.filter(code__contains='_TEST').delete()
        
        # Δημιουργία department types αν δεν υπάρχουν
        kedasy_type, _ = DepartmentType.objects.get_or_create(
            code='KEDASY',
            defaults={'name': 'ΚΕΔΑΣΥ'}
        )
        
        sdei_type, _ = DepartmentType.objects.get_or_create(
            code='SDEI',
            defaults={'name': 'ΣΔΕΥ'}
        )
        
        # Δημιουργία τμημάτων
        kedasy_dept, _ = Department.objects.get_or_create(
            code='KEDASY_TEST',
            defaults={
                'name': 'ΚΕΔΑΣΥ Τεστ',
                'department_type': kedasy_type
            }
        )
        
        sdei_dept, _ = Department.objects.get_or_create(
            code='SDEI_TEST',
            defaults={
                'name': 'ΣΔΕΥ Τεστ',
                'department_type': sdei_type,
                'parent_department': kedasy_dept
            }
        )
        
        # Δημιουργία ρόλων
        manager_role, _ = Role.objects.get_or_create(
            code='MANAGER',
            defaults={'name': 'Προϊστάμενος'}
        )
        employee_role, _ = Role.objects.get_or_create(
            code='EMPLOYEE',
            defaults={'name': 'Υπάλληλος'}
        )
        
        # Δημιουργία χρηστών
        kedasy_manager = User.objects.create_user(
            email='kedasy_manager_test@example.com',
            first_name='Προϊστάμενος',
            last_name='ΚΕΔΑΣΥ',
            department=kedasy_dept,
            is_active=True,
            registration_status='APPROVED'
        )
        kedasy_manager.roles.add(manager_role)
        
        sdei_employee = User.objects.create_user(
            email='sdei_employee_test@example.com',
            first_name='Υπάλληλος',
            last_name='ΣΔΕΥ',
            department=sdei_dept,
            is_active=True,
            registration_status='APPROVED'
        )
        sdei_employee.roles.add(employee_role)
        
        # Δημιουργία τύπου άδειας
        leave_type, _ = LeaveType.objects.get_or_create(
            name='Κανονική Άδεια',
            defaults={'requires_approval': True}
        )
        
        # Δημιουργία αίτησης άδειας από ΣΔΕΥ
        leave_request = LeaveRequest.objects.create(
            user=sdei_employee,
            leave_type=leave_type,
            description='Τεστ αίτηση από ΣΔΕΥ',
            status='SUBMITTED',
            submitted_at=timezone.now()
        )
        
        # Τεστ 1: Έλεγχος αν ο ΚΕΔΑΣΥ manager βλέπει τον ΣΔΕΥ employee
        subordinates = kedasy_manager.get_subordinates()
        self.stdout.write(f"Υφιστάμενοι ΚΕΔΑΣΥ manager: {[u.username for u in subordinates]}")
        
        assert sdei_employee in subordinates, "Ο ΣΔΕΥ υπάλληλος δεν βρέθηκε στους υφισταμένους του ΚΕΔΑΣΥ"
        self.stdout.write(self.style.SUCCESS('✓ Τεστ 1: Ο ΚΕΔΑΣΥ manager βλέπει τον ΣΔΕΥ employee'))
        
        # Τεστ 2: Έλεγχος αν η αίτηση θεωρείται ΚΕΔΑΣΥ/ΚΕΠΕΑ
        assert leave_request.is_kedasy_kepea_department(), "Η αίτηση ΣΔΕΥ δεν αναγνωρίζεται ως ΚΕΔΑΣΥ/ΚΕΠΕΑ"
        self.stdout.write(self.style.SUCCESS('✓ Τεστ 2: Η αίτηση ΣΔΕΥ αναγνωρίζεται ως ΚΕΔΑΣΥ/ΚΕΠΕΑ'))
        
        # Εγκρίνουμε την αίτηση από τον ΚΕΔΑΣΥ manager για να πάει στο PENDING_KEDASY_KEPEA_PROTOCOL
        leave_request.approve_by_manager(kedasy_manager, "Τεστ έγκριση")
        self.stdout.write(f"Νέο status μετά την έγκριση: {leave_request.status}")
        
        # Τεστ 3: Έλεγχος δικαιωμάτων προσθήκης πρωτοκόλλου
        assert leave_request.can_add_kedasy_kepea_protocol(kedasy_manager), "Ο ΚΕΔΑΣΥ manager δεν μπορεί να προσθέσει πρωτόκολλο"
        self.stdout.write(self.style.SUCCESS('✓ Τεστ 3: Ο ΚΕΔΑΣΥ manager μπορεί να προσθέσει πρωτόκολλο'))
        
        # Τεστ 4: Έλεγχος δικαιωμάτων προβολής
        assert leave_request.can_user_view(kedasy_manager), "Ο ΚΕΔΑΣΥ manager δεν μπορεί να δει την αίτηση"
        self.stdout.write(self.style.SUCCESS('✓ Τεστ 4: Ο ΚΕΔΑΣΥ manager μπορεί να δει την αίτηση'))
        
        # Τεστ 5: Έλεγχος επόμενων ενεργειών - Νέα αίτηση που δεν έχει εγκριθεί
        leave_request2 = LeaveRequest.objects.create(
            user=sdei_employee,
            leave_type=leave_type,
            description='Δεύτερη τεστ αίτηση από ΣΔΕΥ',
            status='SUBMITTED',
            submitted_at=timezone.now()
        )
        
        actions = leave_request2.get_next_actions(kedasy_manager)
        assert 'approve' in actions, "Ο ΚΕΔΑΣΥ manager δεν μπορεί να εγκρίνει την αίτηση"
        assert 'reject' in actions, "Ο ΚΕΔΑΣΥ manager δεν μπορεί να απορρίψει την αίτηση"
        self.stdout.write(self.style.SUCCESS('✓ Τεστ 5: Ο ΚΕΔΑΣΥ manager έχει δικαιώματα έγκρισης/απόρριψης'))
        
        # Καθαρισμός δεδομένων
        leave_request.delete()
        leave_request2.delete()
        kedasy_manager.delete()
        sdei_employee.delete()
        sdei_dept.delete()
        kedasy_dept.delete()
        
        self.stdout.write(self.style.SUCCESS('✓ Καθαρισμός δεδομένων ολοκληρώθηκε'))