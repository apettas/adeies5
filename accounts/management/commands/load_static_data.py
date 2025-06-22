from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Role, Department
from leaves.models import LeaveType


class Command(BaseCommand):
    help = 'Φόρτωση στατικών δεδομένων (Ρόλοι, Τμήματα, Τύποι αδειών)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Αναγκαστική ενημέρωση υπαρχόντων δεδομένων',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Φόρτωση στατικών δεδομένων...'))
        
        with transaction.atomic():
            self.load_roles(options['force'])
            self.load_departments(options['force'])
            self.load_leave_types(options['force'])

        self.stdout.write(self.style.SUCCESS('Φόρτωση στατικών δεδομένων ολοκληρώθηκε!'))

    def load_roles(self, force=False):
        """Φόρτωση ρόλων"""
        self.stdout.write('Φόρτωση ρόλων...')
        
        roles_data = [
            {
                'code': 'EMPLOYEE',
                'name': 'Υπάλληλος',
                'description': 'Βασικός ρόλος υπαλλήλου'
            },
            {
                'code': 'MANAGER',
                'name': 'Προϊστάμενος Τμήματος',
                'description': 'Προϊστάμενος τμήματος με δικαιώματα έγκρισης αιτήσεων'
            },
            {
                'code': 'LEAVE_HANDLER',
                'name': 'Χειριστής Αδειών',
                'description': 'Χειριστής αδειών με δικαιώματα επεξεργασίας αιτήσεων'
            },
            {
                'code': 'ADMIN',
                'name': 'Διαχειριστής',
                'description': 'Διαχειριστής συστήματος με πλήρη δικαιώματα'
            },
            {
                'code': 'HR_ADMIN',
                'name': 'Διαχειριστής Ανθρώπινου Δυναμικού',
                'description': 'Διαχειριστής HR με δικαιώματα διαχείρισης προσωπικού'
            }
        ]

        for role_data in roles_data:
            if force:
                role, created = Role.objects.update_or_create(
                    code=role_data['code'],
                    defaults={
                        'name': role_data['name'],
                        'description': role_data['description']
                    }
                )
                action = 'Ενημερώθηκε' if not created else 'Δημιουργήθηκε'
            else:
                role, created = Role.objects.get_or_create(
                    code=role_data['code'],
                    defaults={
                        'name': role_data['name'],
                        'description': role_data['description']
                    }
                )
                action = 'Δημιουργήθηκε' if created else 'Υπάρχει ήδη'
            
            self.stdout.write(f'  {action}: {role.name}')

    def load_departments(self, force=False):
        """Φόρτωση τμημάτων"""
        self.stdout.write('Φόρτωση τμημάτων...')
        
        # Βασικά τμήματα ΠΔΕΔΕ Δυτικής Ελλάδας
        departments_data = [
            {
                'code': 'DIR',
                'name': 'Διεύθυνση',
                'parent': None
            },
            {
                'code': 'ADE',
                'name': 'Αυτοτελής Διεύθυνση Εκπαίδευσης',
                'parent': None
            },
            {
                'code': 'TPE',
                'name': 'Τμήμα Πρωτοβάθμιας Εκπαίδευσης',
                'parent': 'ADE'
            },
            {
                'code': 'TDDE',
                'name': 'Τμήμα Δευτεροβάθμιας Εκπαίδευσης',
                'parent': 'ADE'
            },
            {
                'code': 'TDVE',
                'name': 'Τμήμα Διά Βίου Εκπαίδευσης',
                'parent': 'ADE'
            },
            {
                'code': 'GOD',
                'name': 'Γραφείο Οικονομικής Διοίκησης',
                'parent': 'DIR'
            },
            {
                'code': 'GDY',
                'name': 'Γραφείο Διοικητικής Υποστήριξης',
                'parent': 'DIR'
            },
            {
                'code': 'GIA',
                'name': 'Γραφείο Ιδιωτικής Εκπαίδευσης',
                'parent': 'ADE'
            },
            {
                'code': 'GSE',
                'name': 'Γραφείο Σχολικών Εργαστηρίων',
                'parent': 'TDDE'
            }
        ]

        # Δημιουργία τμημάτων με σειρά ιεραρχίας
        for dept_data in departments_data:
            parent_dept = None
            if dept_data['parent']:
                try:
                    parent_dept = Department.objects.get(code=dept_data['parent'])
                except Department.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f'Γονικό τμήμα {dept_data["parent"]} δεν βρέθηκε για {dept_data["code"]}')
                    )

            if force:
                dept, created = Department.objects.update_or_create(
                    code=dept_data['code'],
                    defaults={
                        'name': dept_data['name'],
                        'is_active': True
                    }
                )
                action = 'Ενημερώθηκε' if not created else 'Δημιουργήθηκε'
            else:
                dept, created = Department.objects.get_or_create(
                    code=dept_data['code'],
                    defaults={
                        'name': dept_data['name'],
                        'is_active': True
                    }
                )
                action = 'Δημιουργήθηκε' if created else 'Υπάρχει ήδη'
            
            self.stdout.write(f'  {action}: {dept.name}')

    def load_leave_types(self, force=False):
        """Φόρτωση τύπων αδειών"""
        self.stdout.write('Φόρτωση τύπων αδειών...')
        
        leave_types_data = [
            {
                'name': 'Κανονική Άδεια',
                'max_days': 25,
                'requires_approval': True,
                'description': 'Κανονική ετήσια άδεια'
            },
            {
                'name': 'Άδεια Ασθενείας',
                'max_days': 30,
                'requires_approval': True,
                'description': 'Άδεια για λόγους υγείας'
            },
            {
                'name': 'Άδεια Μητρότητας',
                'max_days': 119,
                'requires_approval': True,
                'description': 'Άδεια μητρότητας και λοχείας'
            },
            {
                'name': 'Άδεια Πατρότητας',
                'max_days': 14,
                'requires_approval': True,
                'description': 'Άδεια πατρότητας'
            },
            {
                'name': 'Ειδική Άδεια',
                'max_days': 10,
                'requires_approval': True,
                'description': 'Ειδική άδεια για σπουδαίους λόγους'
            },
            {
                'name': 'Εκπαιδευτική Άδεια',
                'max_days': 30,
                'requires_approval': True,
                'description': 'Άδεια για εκπαιδευτικούς σκοπούς'
            },
            {
                'name': 'Έκτακτη Άδεια',
                'max_days': 5,
                'requires_approval': True,
                'description': 'Έκτακτη άδεια για επείγουσες ανάγκες'
            }
        ]

        for leave_type_data in leave_types_data:
            if force:
                leave_type, created = LeaveType.objects.update_or_create(
                    name=leave_type_data['name'],
                    defaults={
                        'max_days': leave_type_data['max_days'],
                        'requires_approval': leave_type_data['requires_approval'],
                        'description': leave_type_data['description'],
                        'is_active': True
                    }
                )
                action = 'Ενημερώθηκε' if not created else 'Δημιουργήθηκε'
            else:
                leave_type, created = LeaveType.objects.get_or_create(
                    name=leave_type_data['name'],
                    defaults={
                        'max_days': leave_type_data['max_days'],
                        'requires_approval': leave_type_data['requires_approval'],
                        'description': leave_type_data['description'],
                        'is_active': True
                    }
                )
                action = 'Δημιουργήθηκε' if created else 'Υπάρχει ήδη'
            
            self.stdout.write(f'  {action}: {leave_type.name}')