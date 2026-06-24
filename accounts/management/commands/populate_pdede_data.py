from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Department, Specialty, Role, Prefecture, Headquarters


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
            self.style.ERROR(
                'Η εντολή populate_pdede_data είναι παρωχημένη (department_type ως string).\n'
                'Χρησιμοποιήστε: python manage.py andreas_static_data'
            )
        )
        return

        self.stdout.write(
            self.style.SUCCESS('🏛️ ΦΟΡΤΩΣΗ ΣΤΑΤΙΚΩΝ ΔΕΔΟΜΕΝΩΝ ΠΔΕΔΕ ΔΥΤΙΚΗΣ ΕΛΛΑΔΟΣ')
        )

        if options['clear']:
            self.clear_existing_data()

        with transaction.atomic():
            # Φόρτωση Specialties
            self.load_specialties()
            
            # Φόρτωση Prefectures
            self.load_prefectures()
            
            # Φόρτωση Headquarters
            self.load_headquarters()
            
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
        Prefecture.objects.all().delete()
        Headquarters.objects.all().delete()
        
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

    def load_prefectures(self):
        """Φόρτωση νομών"""
        self.stdout.write('🌍 Φόρτωση νομών...')
        
        prefectures_data = [
            ('ACHAIA', 'Αχαΐας'),
            ('AITOLOAKARNANIA', 'Αιτωλοακαρνανίας'),
            ('ILIA', 'Ηλείας'),
        ]

        for code, name in prefectures_data:
            prefecture, created = Prefecture.objects.get_or_create(
                code=code,
                defaults={'name': name, 'is_active': True}
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')
            else:
                self.stdout.write(f'  ⚠️ Υπάρχει ήδη: {name}')

    def load_headquarters(self):
        """Φόρτωση εδρών"""
        self.stdout.write('🏢 Φόρτωση εδρών...')
        
        headquarters_data = [
            ('PATRA', 'Πάτρα'),
            ('MESSOLONGI', 'Μεσολόγγι'),
            ('PYRGOS', 'Πύργος'),
            ('KLEITORIA', 'Κλειτορία'),
            ('KRESTENA', 'Κρέστενα'),
            ('ANDRAVIDA', 'Ανδραβίδα'),
        ]

        for code, name in headquarters_data:
            headquarters, created = Headquarters.objects.get_or_create(
                code=code,
                defaults={'name': name, 'is_active': True}
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
                'name': 'Περιφερειακή Διεύθυνση Εκπαίδευσης Δυτικής Ελλάδας ΠΔΕΔΕ',
                'department_type': 'DIRECTION',
                'headquarters': Headquarters.objects.get(code='PATRA'),
                'prefecture': Prefecture.objects.get(code='ACHAIA'),
                'is_active': True,
            }
        )
        if created:
            self.stdout.write('  ✅ Δημιουργήθηκε: Περιφερειακή Διεύθυνση Εκπαίδευσης Δυτικής Ελλάδας ΠΔΕΔΕ')

        # 2. ΑΥΤΟΤΕΛΗΣ ΔΙΕΥΘΗΝΣΗ
        autonomous_direction, created = Department.objects.get_or_create(
            code='AUTO_DIRECTION',
            defaults={
                'name': 'Αυτοτελής Διεύθυνση',
                'department_type': 'AUTONOMOUS_DIRECTION',
                'parent_department': pdede_main,
                'headquarters': Headquarters.objects.get(code='PATRA'),
                'prefecture': Prefecture.objects.get(code='ACHAIA'),
                'is_active': True,
            }
        )
        if created:
            self.stdout.write('  ✅ Δημιουργήθηκε: Αυτοτελής Διεύθυνση')

        # 3. Τμήματα υπό την Αυτοτελή Διεύθυνση
        departments_data = [
            ('TMIMA_A', 'ΤΜΗΜΑ Α', 'DEPARTMENT'),
            ('TMIMA_B', 'ΤΜΗΜΑ Β', 'DEPARTMENT'),
            ('TMIMA_C', 'ΤΜΗΜΑ Γ', 'DEPARTMENT'),
            ('TMIMA_D', 'ΤΜΗΜΑ Δ', 'DEPARTMENT'),
            ('GRAFIO_NOMIKIS', 'ΓΡΑΦΕΙΟ ΝΟΜΙΚΗΣ', 'OFFICE'),
        ]

        for code, name, dept_type in departments_data:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': dept_type,
                    'parent_department': autonomous_direction,
                    'headquarters': Headquarters.objects.get(code='PATRA'),
                    'prefecture': Prefecture.objects.get(code='ACHAIA'),
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')

        # 4. ΚΕ.Δ.Α.Σ.Υ. Services
        kedasy_services = [
            ('KEDASY_1_PATRA', 'ΚΕ.Δ.Α.Σ.Υ. 1ο ΠΑΤΡΑΣ', 'PATRA', 'ACHAIA'),
            ('KEDASY_2_PATRA', 'ΚΕ.Δ.Α.Σ.Υ. 2ο ΠΑΤΡΑΣ', 'PATRA', 'ACHAIA'),
            ('KEDASY_AITOL', 'ΚΕ.Δ.Α.Σ.Υ. ΑΙΤ/ΝΙΑΣ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('KEDASY_ILIA', 'ΚΕ.Δ.Α.Σ.Υ. ΗΛΕΙΑΣ', 'PYRGOS', 'ILIA'),
        ]

        for code, name, headquarters_code, prefecture_code in kedasy_services:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': 'VIRTUAL_DEPARTMENT',
                    'parent_department': pdede_main,
                    'headquarters': Headquarters.objects.get(code=headquarters_code),
                    'prefecture': Prefecture.objects.get(code=prefecture_code),
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')

        # 5. ΚΕΠΕΑ Services
        kepea_services = [
            ('KEPEA_ACHAIA', 'ΚΕΠΕΑ ΑΧΑΪΑΣ', 'KLEITORIA', 'ACHAIA'),
            ('KEPEA_ILIA', 'ΚΕΠΕΑ ΗΛΕΙΑΣ', 'KRESTENA', 'ILIA'),
            ('KEPEA_AITOL', 'ΚΕΠΕΑ ΑΙΤΩΛΟΑΚΑΡΝΑΝΙΑΣ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
        ]

        for code, name, headquarters_code, prefecture_code in kepea_services:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': 'VIRTUAL_DEPARTMENT',
                    'parent_department': pdede_main,
                    'headquarters': Headquarters.objects.get(code=headquarters_code),
                    'prefecture': Prefecture.objects.get(code=prefecture_code),
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')

        # 6. ΚΕΝΤΡΟ ΦΙΛΟΞΕΝΙΑΣ ΠΡΟΣΦΥΓΩΝ - ΑΝΔΡΑΒΙΔΑΣ-ΚΥΛΛΗΝΗΣ
        kfp_andravida, created = Department.objects.get_or_create(
            code='KFP_ANDRAVIDA',
            defaults={
                'name': 'ΚΕΝΤΡΟ ΦΙΛΟΞΕΝΙΑΣ ΠΡΟΣΦΥΓΩΝ - ΑΝΔΡΑΒΙΔΑΣ-ΚΥΛΛΗΝΗΣ',
                'department_type': 'VIRTUAL_DEPARTMENT',
                'parent_department': pdede_main,
                'headquarters': Headquarters.objects.get(code='ANDRAVIDA'),
                'prefecture': Prefecture.objects.get(code='ILIA'),
                'is_active': True,
            }
        )
        if created:
            self.stdout.write('  ✅ Δημιουργήθηκε: ΚΕΝΤΡΟ ΦΙΛΟΞΕΝΙΑΣ ΠΡΟΣΦΥΓΩΝ - ΑΝΔΡΑΒΙΔΑΣ-ΚΥΛΛΗΝΗΣ')

        # 7. ΔΝ/ΤΕΣ ΕΚΠΑΙΔΕΥΣΗΣ
        dntes_ekp, created = Department.objects.get_or_create(
            code='DNTES_EKP',
            defaults={
                'name': 'ΔΝ/ΤΕΣ ΕΚΠΑΙΔΕΥΣΗΣ',
                'department_type': 'VIRTUAL_DEPARTMENT',
                'parent_department': pdede_main,
                'headquarters': Headquarters.objects.get(code='PATRA'),
                'prefecture': Prefecture.objects.get(code='ACHAIA'),
                'is_active': True,
            }
        )
        if created:
            self.stdout.write('  ✅ Δημιουργήθηκε: ΔΝ/ΤΕΣ ΕΚΠΑΙΔΕΥΣΗΣ')

        # 8. Σ.Δ.Ε.Υ. under ΚΕ.Δ.Α.Σ.Υ. 1ο ΠΑΤΡΑΣ
        sdey_kedasy_1_patra = [
            ('SDEY_1_EID_DIM_AIG', 'Σ.Δ.Ε.Υ. 1ο ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΑΙΓΙΟΥ', 'PATRA', 'ACHAIA'),
            ('SDEY_EID_NIP_AIG', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΑΙΓΙΟΥ', 'PATRA', 'ACHAIA'),
            ('SDEY_EEEEK_AIG', 'Σ.Δ.Ε.Υ. Ε.Ε.Ε.ΕΚ ΑΙΓΙΟΥ', 'PATRA', 'ACHAIA'),
            ('SDEY_EID_DIM_KALAV', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΚΑΛΑΒΡΥΤΩΝ', 'PATRA', 'ACHAIA'),
            ('SDEY_2_EID_DIM_PAT', 'Σ.Δ.Ε.Υ. 2ο ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΠΑΤΡΩΝ', 'PATRA', 'ACHAIA'),
            ('SDEY_EID_DIM_KOF_PAT', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΚΩΦΩΝ-ΒΑΡΗΚΟΩΝ ΠΑΤΡΑΣ', 'PATRA', 'ACHAIA'),
            ('SDEY_EEEEK_ACH', 'Σ.Δ.Ε.Υ. Ε.Ε.Ε.Ε.Κ. ΑΧΑΪΑΣ', 'PATRA', 'ACHAIA'),
            ('SDEY_2_EID_NIP_PAT', 'Σ.Δ.Ε.Υ. 2ο ΕΙΔΙΚΟ ΝΗΠΙΑΓΩΓΕΙΟ ΠΑΤΡΑΣ', 'PATRA', 'ACHAIA'),
            ('SDEY_EID_NIP_KOF_PAT', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΚΩΦΩΝ ΠΑΤΡΩΝ', 'PATRA', 'ACHAIA'),
            ('SDEY_48_DIM_PAT', 'Σ.Δ.Ε.Υ. 48ου ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΩΝ', 'PATRA', 'ACHAIA'),
        ]

        kedasy_1_patra = Department.objects.get(code='KEDASY_1_PATRA')
        for code, name, headquarters_code, prefecture_code in sdey_kedasy_1_patra:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': 'VIRTUAL_DEPARTMENT',
                    'parent_department': kedasy_1_patra,
                    'headquarters': Headquarters.objects.get(code=headquarters_code),
                    'prefecture': Prefecture.objects.get(code=prefecture_code),
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')

        # 9. Σ.Δ.Ε.Υ. under ΚΕ.Δ.Α.Σ.Υ. 2ο ΠΑΤΡΑΣ
        sdey_kedasy_2_patra = [
            ('SDEY_EID_DIM_KATO_ACH', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΚΑΤΩ ΑΧΑΙΑΣ', 'PATRA', 'ACHAIA'),
            ('SDEY_44_DIM_PAT', 'Σ.Δ.Ε.Υ. 44ο ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΠΑΤΡΩΝ (ΕΙΔΙΚΟ ΝΗΠΙΑΓΩΓΕΙΟ ΚΑΤΩ ΑΧΑΙΑΣ)', 'PATRA', 'ACHAIA'),
            ('SDEY_1_EID_DIM_PAT', 'Σ.Δ.Ε.Υ. 1ΟΥ ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΩΝ', 'PATRA', 'ACHAIA'),
            ('SDEY_3_EID_DIM_PAT', 'Σ.Δ.Ε.Υ. 3οΥ ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΩΝ - ΠΙΚΠΑ', 'PATRA', 'ACHAIA'),
            ('SDEY_4_EID_DIM_PAT', 'Σ.Δ.Ε.Υ. 4ΟΥ ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΑΣ - ΕΙΔΙΚΟ ΦΑΣΜΑΤΟΣ ΑΥΤΙΣΜΟΥ', 'PATRA', 'ACHAIA'),
            ('SDEY_ENEEGY_L_PAT', 'Σ.Δ.Ε.Υ. ΕΝ.Ε.Ε.ΓΥ.- Λ. ΠΑΤΡΩΝ', 'PATRA', 'ACHAIA'),
            ('SDEY_1_EID_NIP_PAT', 'Σ.Δ.Ε.Υ. 1ου ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΠΑΤΡΑΣ', 'PATRA', 'ACHAIA'),
            ('SDEY_3_EID_NIP_PAT', 'Σ.Δ.Ε.Υ. 3ου ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΠΑΤΡΩΝ', 'PATRA', 'ACHAIA'),
            ('SDEY_39_DIM_PAT', 'Σ.Δ.Ε.Υ. 39ου ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΩΝ', 'PATRA', 'ACHAIA'),
            ('SDEY_61_DIM_PAT', 'Σ.Δ.Ε.Υ. 61ο ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΩΝ', 'PATRA', 'ACHAIA'),
        ]

        kedasy_2_patra = Department.objects.get(code='KEDASY_2_PATRA')
        for code, name, headquarters_code, prefecture_code in sdey_kedasy_2_patra:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': 'VIRTUAL_DEPARTMENT',
                    'parent_department': kedasy_2_patra,
                    'headquarters': Headquarters.objects.get(code=headquarters_code),
                    'prefecture': Prefecture.objects.get(code=prefecture_code),
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')

        # 10. Σ.Δ.Ε.Υ. under ΚΕ.Δ.Α.Σ.Υ. ΑΙΤΩΛΟΑΚΑΡΝΑΝΙΑΣ
        sdey_kedasy_aitol = [
            ('SDEY_1_EID_DIM_AGR', 'Σ.Δ.Ε.Υ. 1ΟΥ ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΑΓΡΙΝΙΟΥ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('SDEY_2_EID_DIM_AGR', 'Σ.Δ.Ε.Υ. 2ΟΥ ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟY ΣΧΟΛΕΙΟΥ ΑΓΡΙΝΙΟΥ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('SDEY_EID_DIM_AGR_MAR', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΑΓΡΙΝΙΟΥ "ΜΑΡΙΑ ΔΗΜΑΔΗ"', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('SDEY_EID_NIP_AGR_MAR', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΑΓΡΙΝΙΟΥ "ΜΑΡΙΑ ΔΗΜΑΔΗ"', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('SDEY_EN_EID_EPAG_AGR', 'Σ.Δ.Ε.Υ. ΕΝΙΑΙΟ ΕΙΔΙΚΟ ΕΠΑΓΓΕΛΜΑΤΙΚΟ ΓΥΜΝΑΣΙΟ - ΛΥΚΕΙΟ ΑΓΡΙΝΙΟΥ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('SDEY_EID_DIM_VON', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΒΟΝΙΤΣΑΣ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('SDEY_EID_DIM_MESS', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΜΕΣΟΛΟΓΓΙΟΥ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('SDEY_EID_NIP_MESS', 'ΕΙΔΙΚΟ ΝΗΠΙΑΓΩΓΕΙΟ ΜΕΣΟΛΟΓΓΙΟΥ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('SDEY_EN_EID_EPAG_MESS', 'Σ.Δ.Ε.Υ. ΕΝΙΑΙΟΥ ΕΙΔΙΚΟΥ ΕΠΑΓΓΕΛΜΑΤΙΚΟΥ ΓΥΜΝΑΣΙΟΥ - ΛΥΚΕΙΟΥ ΜΕΣΟΛΟΓΓΙΟΥ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('SDEY_EID_DIM_NAUP', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟ ΝΑΥΠΑΚΤΟΥ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
            ('SDEY_EEEEK_NAUP', 'ΕΕΕΕΚ ΝΑΥΠΑΚΤΟΣ – ΕΕΕΕΚ', 'MESSOLONGI', 'AITOLOAKARNANIA'),
        ]

        kedasy_aitol = Department.objects.get(code='KEDASY_AITOL')
        for code, name, headquarters_code, prefecture_code in sdey_kedasy_aitol:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': 'VIRTUAL_DEPARTMENT',
                    'parent_department': kedasy_aitol,
                    'headquarters': Headquarters.objects.get(code=headquarters_code),
                    'prefecture': Prefecture.objects.get(code=prefecture_code),
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f'  ✅ Δημιουργήθηκε: {name}')

        # 11. Σ.Δ.Ε.Υ. under ΚΕ.Δ.Α.Σ.Υ. ΗΛΕΙΑΣ
        sdey_kedasy_ilia = [
            ('SDEY_EID_DIM_LECH', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΛΕΧΑΙΝΩΝ', 'PYRGOS', 'ILIA'),
            ('SDEY_DIM_KREST', 'Σ.Δ.Ε.Υ. ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΚΡΕΣΤΕΝΩΝ (ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΚΡΕΣΤΕΝΩΝ)', 'PYRGOS', 'ILIA'),
            ('SDEY_EID_NIP_PIN', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟ ΝΗΠΙΑΓΩΓΕΙΟ ΠΗΝΕΙΟΥ', 'PYRGOS', 'ILIA'),
            ('SDEY_EID_NIP_PYR', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΠΥΡΓΟΥ', 'PYRGOS', 'ILIA'),
            ('SDEY_EID_DIM_PYR', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΥΡΓΟΥ', 'PYRGOS', 'ILIA'),
            ('SDEY_4_FOUFEIO_AMAL', 'Σ.Δ.Ε.Υ. 4/Θ ΦΟΥΦΕΙΟ ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΑΜΑΛΙΑΔΑΣ', 'PYRGOS', 'ILIA'),
            ('SDEY_EN_EID_EPAG_PYR', 'Σ.Δ.Ε.Υ. ΕΝΙΑΙΟΥ ΕΙΔΙΚΟΥ ΕΠΑΓΓΕΛΜΑΤΙΚΟΥ ΓΥΜΝΑΣΙΟΥ-ΛΥΚΕΙΟΥ ΠΥΡΓΟΥ', 'PYRGOS', 'ILIA'),
            ('SDEY_EEEEK_PYR_ILIA', 'Σ.Δ.Ε.Υ. Ε.Ε.Ε.Ε.Κ. ΠΥΡΓΟΥ ΗΛΕΙΑΣ', 'PYRGOS', 'ILIA'),
        ]

        kedasy_ilia = Department.objects.get(code='KEDASY_ILIA')
        for code, name, headquarters_code, prefecture_code in sdey_kedasy_ilia:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': 'VIRTUAL_DEPARTMENT',
                    'parent_department': kedasy_ilia,
                    'headquarters': Headquarters.objects.get(code=headquarters_code),
                    'prefecture': Prefecture.objects.get(code=prefecture_code),
                    'is_active': True,
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
        self.stdout.write(f'  🌍 Prefectures: {Prefecture.objects.count()}')
        self.stdout.write(f'  🏢 Headquarters: {Headquarters.objects.count()}')
