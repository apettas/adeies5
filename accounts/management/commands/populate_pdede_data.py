from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Department, Specialty, Role


class Command(BaseCommand):
    help = 'Φόρτωση στατικών δεδομένων της ΠΔΕΔΕ Δυτικής Ελλάδος'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Διαγραφή υπαρχόντων δεδομένων πριν τη φόρτωση',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🏛️ ΦΟΡΤΩΣΗ ΣΤΑΤΙΚΩΝ ΔΕΔΟΜΕΝΩΝ ΠΔΕΔΕ ΔΥΤΙΚΗΣ ΕΛΛΑΔΟΣ')
        )

        if options['clear']:
            self.clear_existing_data()

        with transaction.atomic():
            # Φόρτωση Specialties
            self.load_specialties()
            
            # Φόρτωση Departments
            self.load_departments()
            
            # Φόρτωση Roles
            self.load_roles()

        self.stdout.write(
            self.style.SUCCESS('✅ Η φόρτωση δεδομένων ολοκληρώθηκε επιτυχώς!')
        )

    def clear_existing_data(self):
        """Διαγραφή υπαρχόντων δεδομένων"""
        self.stdout.write('🗑️ Διαγραφή υπαρχόντων δεδομένων...')
        
        Department.objects.all().delete()
        Specialty.objects.all().delete()
        Role.objects.all().delete()
        
        self.stdout.write(self.style.WARNING('✅ Διαγραφή ολοκληρώθηκε'))

    def load_specialties(self):
        """Φόρτωση εκπαιδευτικών ειδικοτήτων"""
        self.stdout.write('📚 Φόρτωση ειδικοτήτων...')
        
        specialties_data = [
            ('ΠΕ_DIOIT', 'ΠΕ Διοικητικού'),
            ('PE60', 'ΠΕ60 ΝΗΠΙΑΓΩΓΟΙ'),
            ('PE70', 'ΠΕ70 ΔΑΣΚΑΛΟΙ'),
            ('PE02', 'ΠΕ02 ΦΙΛΟΛΟΓΟΙ'),
            ('PE03', 'ΠΕ03 ΜΑΘΗΜΑΤΙΚΟΙ'),
            ('PE04', 'ΠΕ04 ΦΥΣΙΚΟΙ'),
            ('PE05', 'ΠΕ05 ΓΑΛΛΙΚΗΣ ΓΛΩΣΣΑΣ'),
            ('PE06', 'ΠΕ06 ΑΓΓΛΙΚΗΣ ΓΛΩΣΣΑΣ'),
            ('PE07', 'ΠΕ07 ΓΕΡΜΑΝΙΚΗΣ ΓΛΩΣΣΑΣ'),
            ('PE08', 'ΠΕ08 ΚΑΛΛΙΤΕΧΝΙΚΩΝ'),
            ('PE11', 'ΠΕ11 ΜΟΥΣΙΚΗΣ'),
            ('PE16', 'ΠΕ16 ΟΙΚΙΑΚΗΣ ΟΙΚΟΝΟΜΙΑΣ'),
            ('PE17', 'ΠΕ17 ΜΗΧΑΝΟΛΟΓΟΙ'),
            ('PE18', 'ΠΕ18 ΗΛΕΚΤΡΟΛΟΓΟΙ'),
            ('PE19', 'ΠΕ19 ΠΟΛΙΤΙΚΩΝ ΜΗΧΑΝΙΚΩΝ'),
            ('PE20', 'ΠΕ20 ΧΗΜΙΚΩΝ'),
            ('PE32', 'ΠΕ32 ΚΟΙΝΩΝΙΚΗΣ ΕΡΓΑΣΙΑΣ'),
            ('TE01', 'ΤΕ01 ΜΗΧΑΝΟΛΟΓΩΝ'),
            ('TE02', 'ΤΕ02 ΗΛΕΚΤΡΟΛΟΓΩΝ'),
            ('TE03', 'ΤΕ03 ΠΟΛΙΤΙΚΩΝ ΕΡΓΩΝ'),
            ('TE21', 'ΤΕ21 ΟΙΚΟΝΟΜΙΑΣ & ΔΙΟΙΚΗΣΗΣ'),
            ('DE01', 'ΔΕ01 ΔΙΟΙΚΗΤΙΚΟΥ-ΛΟΓΙΣΤΙΚΟΥ'),
            ('DE02', 'ΔΕ02 ΠΡΟΣΩΠΙΚΟΥ ΚΑΘΑΡΙΟΤΗΤΑΣ'),
            ('DE03', 'ΔΕ03 ΟΔΗΓΩΝ'),
            ('OTHER_SPEC', 'ΆΛΛΗ ΕΙΔΙΚΟΤΗΤΑ'),
        ]

        for code, name in specialties_data:
            specialty, created = Specialty.objects.get_or_create(
                specialties_short=code,
                defaults={'specialties_full': name, 'is_active': True}
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')
            else:
                self.stdout.write(f'  ⚠️ Υπάρχει ήδη: {name}')

    def load_departments(self):
        """Φόρτωση οργανογράμματος ΠΔΕΔΕ"""
        self.stdout.write('🏢 Φόρτωση οργανογράμματος...')
        
        # 1. ΠΔΕΔΕ (Main Directorate)
        pdede_main, created = Department.objects.get_or_create(
            code='PDEDE_MAIN',
            defaults={
                'name': 'ΠΔΕΔΕ Δυτικής Ελλάδος',
                'department_type': 'DIRECTION',
                'headquarters': 'PATRA',
                'prefecture': 'ACHAIA',
                'is_active': True
            }
        )
        if created:
            self.stdout.write('  ✅ Δημιουργήθηκε: ΠΔΕΔΕ Δυτικής Ελλάδος')

        # 2. ΑΥΤΟΤΕΛΗΣ ΔΙΕΥΘΗΝΣΗ
        autonomous_direction, created = Department.objects.get_or_create(
            code='AUTO_DIRECTION',
            defaults={
                'name': 'Αυτοτελής Διεύθυνση',
                'department_type': 'AUTONOMOUS_DIRECTION',
                'parent_department': pdede_main,
                'headquarters': 'PATRA',
                'prefecture': 'ACHAIA',
                'is_active': True
            }
        )
        if created:
            self.stdout.write('  ✅ Δημιουργήθηκε: Αυτοτελής Διεύθυνση')

        # 3. Τμήματα υπό την Αυτοτελή Διεύθυνση
        departments_data = [
            ('TMIMA_A', 'ΤΜΗΜΑ Α'),
            ('TMIMA_B', 'ΤΜΗΜΑ Β'),
            ('TMIMA_C', 'ΤΜΗΜΑ Γ'),
            ('TMIMA_D', 'ΤΜΗΜΑ Δ'),
            ('GRAFIO_NOMIKIS', 'ΓΡΑΦΕΙΟ ΝΟΜΙΚΗΣ'),
        ]

        for code, name in departments_data:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': 'DEPARTMENT' if 'ΤΜΗΜΑ' in name else 'OFFICE',
                    'parent_department': autonomous_direction,
                    'headquarters': 'PATRA',
                    'prefecture': 'ACHAIA',
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')

        # 4. ΚΕ.Δ.Α.Σ.Υ. Services
        kedasy_services = [
            ('KEDASY_1_PATRA', '1ο ΚΕ.Δ.Α.Σ.Υ. ΠΑΤΡΑΣ', 'PATRA', 'ACHAIA'),
            ('KEDASY_2_PATRA', '2ο ΚΕ.Δ.Α.Σ.Υ. ΠΑΤΡΑΣ', 'PATRA', 'ACHAIA'),
            ('KEDASY_AITOL', 'ΚΕ.Δ.Α.Σ.Υ. ΑΙΤ/ΝΙΑΣ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('KEDASY_ILIA', 'ΚΕ.Δ.Α.Σ.Υ. ΗΛΕΙΑΣ', 'PYRGOS', 'ILIA'),
        ]

        for code, name, headquarters, prefecture in kedasy_services:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': 'VIRTUAL_DEPARTMENT',
                    'parent_department': pdede_main,
                    'headquarters': headquarters,
                    'prefecture': prefecture,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')

        # 5. ΚΕΠΕΑ Services
        kepea_services = [
            ('KEPEA_ACHAIA', 'ΚΕΠΕΑ ΑΧΑΪΑΣ', 'PATRA', 'ACHAIA'),
            ('KEPEA_ILIA', 'ΚΕΠΕΑ ΗΛΕΙΑΣ', 'PYRGOS', 'ILIA'),
            ('KEPEA_AITOL', 'ΚΕΠΕΑ ΑΙΤ/ΝΙΑΣ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
        ]

        for code, name, headquarters, prefecture in kepea_services:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': 'VIRTUAL_DEPARTMENT',
                    'parent_department': pdede_main,
                    'headquarters': headquarters,
                    'prefecture': prefecture,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')

    def load_roles(self):
        """Φόρτωση ρόλων χρηστών"""
        self.stdout.write('👥 Φόρτωση ρόλων...')
        
        roles_data = [
            ('ADMIN', 'Διαχειριστής Συστήματος', 'Πλήρη δικαιώματα διαχείρισης'),
            ('MANAGER', 'Προϊστάμενος Τμήματος', 'Διαχείριση αδειών τμήματος'),
            ('HR_OFFICER', 'Υπεύθυνος Προσωπικού', 'Διαχείριση προσωπικού και αδειών'),
            ('EMPLOYEE', 'Υπάλληλος', 'Υποβολή αιτήσεων άδειας'),
            ('SECRETARY', 'Γραμματέας', 'Υποστήριξη και καταχώρηση στοιχείων'),
        ]

        for code, name, description in roles_data:
            role, created = Role.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': description,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')
            else:
                self.stdout.write(f'  ⚠️ Υπάρχει ήδη: {name}')

        self.stdout.write('\n📊 ΣΤΑΤΙΣΤΙΚΑ ΦΟΡΤΩΣΗΣ:')
        self.stdout.write(f'  🏢 Departments: {Department.objects.count()}')
        self.stdout.write(f'  📚 Specialties: {Specialty.objects.count()}')
        self.stdout.write(f'  👥 Roles: {Role.objects.count()}')