from django.core.management.base import BaseCommand
from accounts.models import User, Department, DepartmentType
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Test the new hierarchical approval logic for AUTOTELOUS_DN departments'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing Hierarchical Approval Logic'))
        self.stdout.write('=' * 60)

        # 1. Βρίσκουμε την Αυτοτελή Διεύθυνση
        try:
            autotelous_dn = Department.objects.get(code='AUTOTELOUS_DN')
            self.stdout.write(f'\n🏛️  Αυτοτελής Διεύθυνση: {autotelous_dn.name}')
            
            # Βρίσκουμε τον προϊστάμενο της Αυτοτελούς Διεύθυνσης
            autotelous_managers = User.objects.filter(
                department=autotelous_dn,
                roles__code='MANAGER',
                is_active=True
            ).distinct()
            
            self.stdout.write(f'📋 Προϊστάμενοι Αυτοτελούς Διεύθυνσης: {[m.full_name for m in autotelous_managers]}')
            
        except Department.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ Δεν βρέθηκε η Αυτοτελής Διεύθυνση'))
            return

        # 2. Βρίσκουμε το Τμήμα Δ υπό την Αυτοτελή Διεύθυνση
        try:
            tmima_d = Department.objects.get(code='TMIMA_D')
            self.stdout.write(f'\n🏢 Τμήμα Δ: {tmima_d.name}')
            self.stdout.write(f'🔗 Parent: {tmima_d.parent_department.name if tmima_d.parent_department else "None"}')
            
            # Βρίσκουμε τον προϊστάμενο του Τμήματος Δ
            tmima_d_managers = User.objects.filter(
                department=tmima_d,
                roles__code='MANAGER',
                is_active=True
            ).distinct()
            
            self.stdout.write(f'📋 Προϊστάμενοι Τμήματος Δ: {[m.full_name for m in tmima_d_managers]}')
            
        except Department.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ Δεν βρέθηκε το Τμήμα Δ'))
            return

        # 3. Βρίσκουμε το κύριο ΠΔΕΔΕ
        try:
            main_pdede = Department.objects.get(code='PDEDE')
            self.stdout.write(f'\n🏛️  Κύριο ΠΔΕΔΕ: {main_pdede.name}')
            
            # Βρίσκουμε τον προϊστάμενο του κύριου ΠΔΕΔΕ
            main_pdede_managers = User.objects.filter(
                department=main_pdede,
                roles__code='MANAGER',
                is_active=True
            ).distinct()
            
            self.stdout.write(f'📋 Προϊστάμενοι Κύριου ΠΔΕΔΕ: {[m.full_name for m in main_pdede_managers]}')
            
        except Department.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ Δεν βρέθηκε το κύριο ΠΔΕΔΕ'))
            return

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('Testing Approval Hierarchy for Users'))
        self.stdout.write('=' * 60)

        # 4. Δοκιμάζουμε τη λογική για διάφορους χρήστες
        # Παίρνουμε χρήστες από διάφορα τμήματα
        test_users = User.objects.filter(
            is_active=True,
            department__isnull=False
        ).select_related('department', 'department__parent_department').distinct()[:10]

        for user in test_users:
            self.stdout.write(f'\n👤 {user.full_name}')
            self.stdout.write(f'   📍 Τμήμα: {user.department.name} ({user.department.code})')
            self.stdout.write(f'   📊 Ρόλοι: {[role.name for role in user.roles.all()]}')
            
            # Δοκιμάζουμε get_approving_manager()
            approving_manager = user.get_approving_manager()
            if approving_manager:
                self.stdout.write(f'   ✅ Προϊστάμενος έγκρισης: {approving_manager.full_name} ({approving_manager.department.name})')
            else:
                self.stdout.write(f'   ❌ Δεν βρέθηκε προϊστάμενος έγκρισης')
            
            # Δοκιμάζουμε can_request_leave()
            can_request = user.can_request_leave()
            if can_request:
                self.stdout.write(f'   ✅ Μπορεί να αιτηθεί άδεια')
            else:
                self.stdout.write(f'   ❌ ΔΕΝ μπορεί να αιτηθεί άδεια')

        # 5. Ειδικές δοκιμές για την ιεραρχία AUTOTELOUS_DN
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('Specific Tests for AUTOTELOUS_DN Hierarchy'))
        self.stdout.write('=' * 60)

        # Δοκιμάζουμε την ιεραρχία
        departments_to_test = [
            ('TMIMA_D', 'Τμήμα Δ'),
            ('AUTOTELOUS_DN', 'Αυτοτελής Διεύθυνση'),
            ('PDEDE', 'Κύριο ΠΔΕΔΕ'),
        ]

        for dept_code, dept_name in departments_to_test:
            try:
                dept = Department.objects.get(code=dept_code)
                self.stdout.write(f'\n🏢 {dept_name}:')
                
                # Βρίσκουμε χρήστες σε αυτό το τμήμα
                dept_users = User.objects.filter(
                    department=dept,
                    is_active=True
                ).select_related('department')
                
                for user in dept_users:
                    self.stdout.write(f'   👤 {user.full_name}')
                    self.stdout.write(f'      📊 Ρόλοι: {[role.name for role in user.roles.all()]}')
                    
                    approving_manager = user.get_approving_manager()
                    if approving_manager:
                        self.stdout.write(f'      ✅ Εγκρίνεται από: {approving_manager.full_name} ({approving_manager.department.name})')
                    else:
                        self.stdout.write(f'      ❌ Δεν βρέθηκε προϊστάμενος')
                    
                    can_request = user.can_request_leave()
                    status = "✅ Μπορεί" if can_request else "❌ ΔΕΝ μπορεί"
                    self.stdout.write(f'      {status} να αιτηθεί άδεια')
                    
            except Department.DoesNotExist:
                self.stdout.write(f'❌ Δεν βρέθηκε το τμήμα {dept_code}')

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('Testing Complete!'))
        self.stdout.write('=' * 60)