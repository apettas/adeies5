from django.core.management.base import BaseCommand
from leaves.models import Logo, Info, LeaveType, Signee, Ypopsin
from accounts.models import Headquarters, Specialty, Prefecture, Role, DepartmentType, Department


class Command(BaseCommand):
    help = 'Φορτώνει static data στη βάση δεδομένων'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Έναρξη φόρτωσης static data...'))
        
        # Φόρτωση δεδομένων
        self.load_logos()
        self.load_info()
        self.load_leave_types()
        self.load_signees()
        self.load_ypopsin()
        self.load_headquarters()
        self.load_specialties()
        self.load_prefectures()
        self.load_roles()
        self.load_department_types()
        self.load_departments()
        
        self.stdout.write(self.style.SUCCESS('Ολοκλήρωση φόρτωσης static data!'))

    def load_logos(self):
        """Φόρτωση λογότυπων"""
        self.stdout.write('Φόρτωση λογότυπων...')
        
        logos_data = [
            {
                'logo_short': 'ΤΡΕΧΟΝ 2025',
                'logo': '''ΕΛΛΗΝΙΚΗ ΔΗΜΟΚΡΑΤΙΑ
ΥΠΟΥΡΓΕΙΟ ΠΑΙΔΕΙΑΣ, ΘΡΗΣΚΕΥΜΑΤΩΝ ΚΑΙ ΑΘΛΗΤΙΣΜΟΥ
ΠΕΡΙΦΕΡΕΙΑΚΗ ΔΙΕΥΘΥΝΣΗ
Π/ΘΜΙΑΣ & Δ/ΘΜΙΑΣ ΕΚΠΑΙΔΕΥΣΗΣ ΔΥΤΙΚΗΣ ΕΛΛΑΔΑΣ
ΑΥΤΟΤΕΛΗΣ ΔΙΕΥΘΥΝΣΗ ΔΙΟΙΚΗΤΙΚΗΣ,
ΟΙΚΟΝΟΜΙΚΗΣ ΚΑΙ ΠΑΙΔΑΓΩΓΙΚΗΣ ΥΠΟΣΤΗΡΙΞΗΣ
ΤΜΗΜΑ Γ' ΠΡΟΣΩΠΙΚΟΥ''',
                'is_active': True
            }
        ]
        
        for logo_data in logos_data:
            logo, created = Logo.objects.get_or_create(
                logo_short=logo_data['logo_short'],
                defaults={
                    'logo': logo_data['logo'],
                    'is_active': logo_data['is_active']
                }
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε λογότυπο: {logo.logo_short}')
            else:
                self.stdout.write(f'  Λογότυπο υπάρχει ήδη: {logo.logo_short}')

    def load_info(self):
        """Φόρτωση πληροφοριών"""
        self.stdout.write('Φόρτωση πληροφοριών...')
        
        info_data = [
            {
                'info_short': 'Κορσιάνου Αικατερίνη',
                'info': '''Ταχ. διεύθυνση : Ακτής Δυμαίων 25α, Πάτρα
Ταχ. κώδικας : 26222
Ταχ. θυρίδα : 2540
Πληροφορίες : Α. Κορσιάνου
Τηλέφωνο : 2610–362423
Ηλ. Ταχυδρομείο : pdede@sch.gr''',
                'is_active': True
            }
        ]
        
        for info_item in info_data:
            info, created = Info.objects.get_or_create(
                info_short=info_item['info_short'],
                defaults={
                    'info': info_item['info'],
                    'is_active': info_item['is_active']
                }
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκαν πληροφορίες: {info.info_short}')
            else:
                self.stdout.write(f'  Πληροφορίες υπάρχουν ήδη: {info.info_short}')

    def load_leave_types(self):
        """Φόρτωση τύπων αδειών"""
        self.stdout.write('Φόρτωση τύπων αδειών...')
        
        leave_types_data = [
            {'name': '1 Κανονική Άδεια', 'description': 'Κανονική Άδεια', 'max_days': 25, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση κανονικής άδειας', 'decision_text': 'κανονική άδεια', 'folder': 'Φ 12.1/', 'general_category': 'Κανονικές Άδειες'},
            {'name': '2α Αναρρωτική Άδεια με ΥΔ', 'description': 'Αναρρωτική Άδεια με ΥΔ', 'max_days': 15, 'requires_approval': False, 'is_active': True, 'subject_text': 'Χορήγηση αναρρωτικής άδειας', 'decision_text': 'αναρρωτική άδεια', 'folder': 'Φ 12.2/', 'general_category': 'Αναρρωτικές Άδειες'},
            {'name': '2β Αναρρωτική Άδεια με Ιατρική Γνωμάτευση', 'description': 'Αναρρωτική Άδεια με Ιατρική Γνωμάτευση', 'max_days': 20, 'requires_approval': False, 'is_active': True, 'subject_text': 'Χορήγηση αναρρωτικής άδειας', 'decision_text': 'αναρρωτική άδεια', 'folder': 'Φ 12.2/', 'general_category': 'Αναρρωτικές Άδειες'},
            {'name': '2γ Αναρρωτική Άδεια με απόφ. Υγειονομικής Επιτροπής', 'description': 'Αναρρωτική Άδεια με απόφ. Υγειονομικής Επιτροπής', 'max_days': 30, 'requires_approval': False, 'is_active': True, 'subject_text': 'Χορήγηση αναρρωτικής άδειας', 'decision_text': 'αναρρωτική άδεια', 'folder': 'Φ 12.2/', 'general_category': 'Αναρρωτικές Άδειες'},
            {'name': '3 Άδεια αιμοδοσίας', 'description': 'Άδεια αιμοδοσίας', 'max_days': 2, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας αιμοδοσίας', 'decision_text': 'άδεια αιμοδοσίας', 'folder': 'Φ 12.4/', 'general_category': 'Άδειες Αιμοδοσίας'},
            {'name': '4 Άδεια για την παρακολούθηση της σχολικής επίδοσης των τέκνων', 'description': 'Άδεια για την παρακολούθηση της σχολικής επίδοσης των τέκνων', 'max_days': 4, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας για την παρακολούθηση της σχολικής επίδοσης των τέκνων', 'decision_text': 'άδεια για την παρακολούθηση της σχολικής επίδοσης των τέκνων', 'folder': 'Φ 12.3/', 'general_category': 'Γονικές Άδειες'},
            {'name': '5 Άδεια για επιμορφωτικούς ή επιστημονικούς λόγους', 'description': 'Άδεια για επιμορφωτικούς ή επιστημονικούς λόγους', 'max_days': 30, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας για επιμορφωτικούς ή επιστημονικούς λόγους', 'decision_text': 'άδεια για επιμορφωτικούς ή επιστημονικούς λόγους', 'folder': 'Φ 12.6/', 'general_category': 'Επιμορφωτικές Άδειες'},
            {'name': 'Άδεια Αναπηρίας', 'description': 'Άδεια Αναπηρίας', 'max_days': 10, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας αναπηρίας', 'decision_text': 'άδεια αναπηρίας', 'folder': 'Φ.12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια Γάμου', 'description': 'Άδεια Γάμου', 'max_days': 5, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας γάμου', 'decision_text': 'άδεια γάμου', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια Γέννησης Τέκνου', 'description': 'Άδεια Γέννησης Τέκνου', 'max_days': 2, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας γέννησης τέκνου', 'decision_text': 'άδεια γέννησης τέκνου', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια άσκησης εκλογικού δικαιώματος', 'description': 'Άδεια άσκησης εκλογικού δικαιώματος', 'max_days': 1, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας άσκησης εκλογικού δικαιώματος', 'decision_text': 'άδεια άσκησης εκλογικού δικαιώματος', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια αιρετών ΟΤΑ Α\' & Β΄ βαθμού', 'description': 'Άδεια αιρετών ΟΤΑ Α\' & Β΄ βαθμού', 'max_days': 20, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας αιρετών ΟΤΑ Α\' & Β΄ βαθμού', 'decision_text': 'άδεια αιρετών ΟΤΑ Α\' & Β΄ βαθμού', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια αναπηρίας', 'description': 'Άδεια αναπηρίας', 'max_days': 10, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας αναπηρίας', 'decision_text': 'άδεια αναπηρίας', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια ανατροφής τέκνου', 'description': 'Άδεια ανατροφής τέκνου', 'max_days': 120, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση Άδειας ανατροφής τέκνου', 'decision_text': 'άδεια ανατροφής τέκνου', 'folder': 'Φ 12.5/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια ασθένειας τέκνων', 'description': 'Άδεια ασθένειας τέκνων', 'max_days': 14, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας ασθένειας τέκνων', 'decision_text': 'άδεια ασθένειας τέκνων', 'folder': 'Φ 12.2/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια για συμμετοχή σε δίκη', 'description': 'Άδεια για συμμετοχή σε δίκη', 'max_days': 2, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας για συμμετοχή σε δίκη', 'decision_text': 'άδεια για συμμετοχή σε δίκη', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια γυναικολογικού ελέγχου', 'description': 'Άδεια γυναικολογικού ελέγχου', 'max_days': 1, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας γυναικολογικού ελέγχου', 'decision_text': 'άδεια γυναικολογικού ελέγχου', 'folder': 'Φ.12.11/', 'general_category': 'Αναρρωτικές Άδειες'},
            {'name': 'Άδεια ειδικού σκοπού', 'description': 'Άδεια ειδικού σκοπού', 'max_days': 5, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας ειδικού σκοπού', 'decision_text': 'άδεια ειδικού σκοπου', 'folder': 'Φ.12.10/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια ειδικού σκοπού λόγω νόσησης τέκνου με κορωνοϊό COVID-19', 'description': 'Άδεια ειδικού σκοπού λόγω νόσησης τέκνου με κορωνοϊό COVID-19', 'max_days': 14, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας ειδικού σκοπού λόγω νόσησης τέκνου με κορωνοϊό COVID-19', 'decision_text': 'άδεια ειδικού σκοπού λόγω νόσησης τέκνου με κορωνοϊό COVID-19', 'folder': 'Φ 12.10/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια εξετάσεων', 'description': 'Άδεια εξετάσεων', 'max_days': 14, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας εξετάσεων', 'decision_text': 'άδεια εξετάσεων', 'folder': 'Φ 12.6/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια κύησης', 'description': 'Άδεια κύησης', 'max_days': 60, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας κύησης', 'decision_text': 'άδεια κύησης', 'folder': 'Φ 12.5/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια λοχείας', 'description': 'Άδεια λοχείας', 'max_days': 60, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας λοχείας', 'decision_text': 'άδεια λοχείας', 'folder': 'Φ 12.5/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια νοσήματος', 'description': 'Άδεια νοσήματος', 'max_days': 30, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας νοσήματος', 'decision_text': 'άδεια νοσήματος', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια νοσήματος τέκνου', 'description': 'Άδεια νοσήματος τέκνου', 'max_days': 30, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας νοσήματος τέκνου', 'decision_text': 'άδεια νοσήματος τέκνου', 'folder': 'Φ.12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια προγεννητικού ελέγχου', 'description': 'Άδεια προγεννητικού ελέγχου', 'max_days': 7, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας προγεννητικού ελέγχου', 'decision_text': 'άδεια προγεννητικού ελέγχου', 'folder': 'Φ 12.5/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Άδεια χωρίς αποδοχές', 'description': 'Άδεια χωρίς αποδοχές', 'max_days': 365, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας χωρίς αποδοχές', 'decision_text': 'άδεια χωρίς αποδοχές', 'folder': 'Φ 12.8/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Αναρρωτική άδεια ειδικού σκοπού', 'description': 'Αναρρωτική άδεια ειδικού σκοπού', 'max_days': 10, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση αναρρωτικής άδεια ειδικού σκοπού', 'decision_text': 'αναρρωτική άδεια ειδικού σκοπού', 'folder': 'Φ.12.10/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Γονική Άδεια (Ν.4808/2021)', 'description': 'Γονική Άδεια (Ν.4808/2021)', 'max_days': 120, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση Γονικής Άδειας (Ν.4808/2021)', 'decision_text': 'Γονική Άδεια (Ν.4808/2021)', 'folder': 'Φ 12.5/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Ειδική άδεια ανυπαίτιου κωλύματος', 'description': 'Ειδική άδεια ανυπαίτιου κωλύματος', 'max_days': 5, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση ειδικής άδειας ανυπαίτιου κωλύματος', 'decision_text': 'ειδική άδεια ανυπαίτιου κωλύματος', 'folder': 'Φ 12.5/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Ειδική άδεια απουσίας ομάδων αυξημένου κινδύνου', 'description': 'Ειδική άδεια απουσίας ομάδων αυξημένου κινδύνου', 'max_days': 30, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση ειδικής άδειας απουσίας ομάδων αυξημένου κινδύνου', 'decision_text': 'ειδική άδεια απουσίας ομάδων αυξημένου κινδύνου', 'folder': 'Φ.12.11/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Ειδική άδεια διευκόλυνσης', 'description': 'Ειδική άδεια διευκόλυνσης', 'max_days': 5, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση Ειδικής άδειας διευκόλυνσης', 'decision_text': 'υποψήφιο αιρετό εκπρόσωπο για το Περιφερειακό Υπηρεσιακό Συμβούλιο Διοικητικού Προσωπικού (ΠΥΣΔΥΠ) Δυτικής Ελλάδας, άδεια ειδική διευκόλυνσης', 'folder': 'Φ 12.5/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Ειδική άδεια(θανάτου)', 'description': 'θανάτου', 'max_days': 3, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση Ειδικής άδειας λόγω θανάτου συγγενούς', 'decision_text': 'ειδική άδεια λόγω θανάτου συγγενούς', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Εορταστική Άδεια', 'description': 'Εορταστική Άδεια', 'max_days': 2, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση εορταστικής άδειας', 'decision_text': 'εορταστική άδεια', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Κανονική Άδεια', 'description': '', 'max_days': 30, 'requires_approval': True, 'is_active': True, 'subject_text': '', 'decision_text': '', 'folder': '', 'general_category': ''},
            {'name': 'Μονογονεϊκή Άδεια', 'description': 'Μονογονεϊκή Άδεια', 'max_days': 6, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση Μονογονεϊκής Άδειας', 'decision_text': 'μονογονεϊκή άδεια', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Πατρότητας', 'description': 'Πατρότητας (Ν.4808/2021)', 'max_days': 14, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση Άδειας Πατρότητας (Ν.4808/2021)', 'decision_text': 'Άδεια Πατρότητας (Ν.4808/2021)', 'folder': 'Φ 12.5/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Συνδικαλιστική Άδεια', 'description': 'Συνδικαλιστική Άδεια', 'max_days': 10, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση συνδικαλιστικής άδεια', 'decision_text': 'συνδικαλιστική άδεια', 'folder': 'Φ 12.4/', 'general_category': 'Άλλες Άδειες'},
            {'name': 'Υποβολής σε ιατρικές μεθόδους υποβοηθούμενης αναπαραγωγής', 'description': 'Υποβολής σε ιατρικές μεθόδους υποβοηθούμενης αναπαραγωγής', 'max_days': 7, 'requires_approval': True, 'is_active': True, 'subject_text': 'Χορήγηση άδειας Υποβολής σε ιατρικές μεθόδους υποβοηθούμενης αναπαραγωγής', 'decision_text': 'άδεια Υποβολής σε ιατρικές μεθόδους υποβοηθούμενης αναπραγωγής', 'folder': 'Φ 12.5/', 'general_category': 'Άλλες Άδειες'}
        ]
        
        for leave_type_data in leave_types_data:
            leave_type, created = LeaveType.objects.get_or_create(
                name=leave_type_data['name'],
                defaults=leave_type_data
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε τύπος άδειας: {leave_type.name}')

    def load_signees(self):
        """Φόρτωση υπογραφόντων"""
        self.stdout.write('Φόρτωση υπογραφόντων...')
        
        signees_data = [
            {'signee_name': 'Αναστάσιος Παντελιάδης', 'signee_short': 'Διευθυντής', 'is_active': True},
            {'signee_name': 'Αικατερίνη Κορσιάνου', 'signee_short': 'Προϊσταμένη', 'is_active': True}
        ]
        
        for signee_data in signees_data:
            signee, created = Signee.objects.get_or_create(
                signee_name=signee_data['signee_name'],
                defaults=signee_data
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε υπογράφων: {signee.signee_name}')
            else:
                self.stdout.write(f'  Υπογράφων υπάρχει ήδη: {signee.signee_name}')

    def load_ypopsin(self):
        """Φόρτωση υπόψιν δεδομένων"""
        self.stdout.write('Φόρτωση υπόψιν δεδομένων...')
        
        # Βασικά υπόψιν δεδομένα
        ypopsin_data = [
            {
                'ypopsin_short': 'Κανονική Άδεια',
                'ypopsin': 'Υπόψιν: Το άρθρο 24 παρ. 1 του Ν.4808/2021 (ΦΕΚ 101/Α/2021).',
                'is_active': True
            },
            {
                'ypopsin_short': 'Αναρρωτική Άδεια',
                'ypopsin': 'Υπόψιν: Το άρθρο 34 παρ. 1 του Ν.4808/2021 (ΦΕΚ 101/Α/2021).',
                'is_active': True
            }
        ]
        
        for ypopsin_item in ypopsin_data:
            ypopsin, created = Ypopsin.objects.get_or_create(
                ypopsin_short=ypopsin_item['ypopsin_short'],
                defaults={
                    'ypopsin': ypopsin_item['ypopsin'],
                    'is_active': ypopsin_item['is_active']
                }
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε υπόψιν: {ypopsin.ypopsin_short}')
            else:
                self.stdout.write(f'  Υπόψιν υπάρχει ήδη: {ypopsin.ypopsin_short}')

    def load_headquarters(self):
        """Φόρτωση έδρας"""
        self.stdout.write('Φόρτωση έδρας...')
        
        headquarters_data = [
            {'name': 'Πάτρα', 'code': 'PATRA'},
            {'name': 'Αγρίνιο', 'code': 'AGRINIO'},
            {'name': 'Μεσολόγγι', 'code': 'MESOLONGI'},
            {'name': 'Πύργος', 'code': 'PYRGOS'},
            {'name': 'Λευκάδα', 'code': 'LEFKADA'},
            {'name': 'Κλειτορία', 'code': 'KLEITORIA'},
            {'name': 'Κρέστενα', 'code': 'KRESTENA'},
            {'name': 'Ανδραβίδα', 'code': 'ANDRAVIDA'}
        ]
        
        for hq_data in headquarters_data:
            headquarters, created = Headquarters.objects.get_or_create(
                code=hq_data['code'],
                defaults={'name': hq_data['name']}
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε έδρα: {headquarters.name}')
            else:
                self.stdout.write(f'  Έδρα υπάρχει ήδη: {headquarters.name}')

    def load_specialties(self):
        """Φόρτωση ειδικοτήτων"""
        self.stdout.write('Φόρτωση ειδικοτήτων...')
        
        specialties_data = [
            {'specialties_full': 'ΠΕ01 - Θεολόγων', 'specialties_short': 'PE01'},
            {'specialties_full': 'ΠΕ02 - Φιλολόγων', 'specialties_short': 'PE02'},
            {'specialties_full': 'ΠΕ03 - Μαθηματικών', 'specialties_short': 'PE03'},
            {'specialties_full': 'ΠΕ11 - Δασκάλων', 'specialties_short': 'PE11'},
            {'specialties_full': 'ΠΕ12 - Νηπιαγωγών', 'specialties_short': 'PE12'},
            {'specialties_full': 'ΔΕ - Διοικητικού', 'specialties_short': 'DE'},
            {'specialties_full': 'ΥΕ - Υπηρετικού', 'specialties_short': 'YE'}
        ]
        
        for specialty_data in specialties_data:
            specialty, created = Specialty.objects.get_or_create(
                specialties_full=specialty_data['specialties_full'],
                defaults={'specialties_short': specialty_data['specialties_short']}
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε ειδικότητα: {specialty.specialties_full}')
            else:
                self.stdout.write(f'  Ειδικότητα υπάρχει ήδη: {specialty.specialties_full}')

    def load_prefectures(self):
        """Φόρτωση νομών"""
        self.stdout.write('Φόρτωση νομών...')
        
        prefectures_data = [
            {'name': 'Αιτωλοακαρνανίας', 'code': 'AIT'},
            {'name': 'Αχαΐας', 'code': 'ACH'},
            {'name': 'Ηλείας', 'code': 'HLE'},
            {'name': 'Λευκάδας', 'code': 'LEU'}
        ]
        
        for prefecture_data in prefectures_data:
            prefecture, created = Prefecture.objects.get_or_create(
                code=prefecture_data['code'],
                defaults={'name': prefecture_data['name']}
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε νομός: {prefecture.name}')
            else:
                self.stdout.write(f'  Νομός υπάρχει ήδη: {prefecture.name}')
    def load_roles(self):
        """Φόρτωση ρόλων"""
        self.stdout.write('Φόρτωση ρόλων...')
        
        roles_data = [
            {
                'code': 'EMPLOYEE',
                'name': 'Υπάλληλος',
                'description': 'Βασικός ρόλος υπαλλήλου',
                'is_active': True
            },
            {
                'code': 'MANAGER',
                'name': 'Προϊστάμενος Τμήματος',
                'description': 'Προϊστάμενος τμήματος με δικαιώματα έγκρισης αιτήσεων',
                'is_active': True
            },
            {
                'code': 'LEAVE_HANDLER',
                'name': 'Χειριστής Αδειών',
                'description': 'Χειριστής αδειών με δικαιώματα επεξεργασίας αιτήσεων',
                'is_active': True
            },
            {
                'code': 'ADMIN',
                'name': 'Διαχειριστής',
                'description': 'Διαχειριστής συστήματος με πλήρη δικαιώματα',
                'is_active': True
            },
            {
                'code': 'HR_ADMIN',
                'name': 'Διαχειριστής Ανθρώπινου Δυναμικού',
                'description': 'Διαχειριστής HR με δικαιώματα διαχείρισης προσωπικού',
                'is_active': True
            },
            {
                'code': 'HR_OFFICER',
                'name': 'Υπεύθυνος Προσωπικού',
                'description': 'Διαχείριση προσωπικού και αδειών',
                'is_active': True
            },
            {
                'code': 'SECRETARY',
                'name': 'Γραμματέας',
                'description': 'Υποστήριξη και καταχώρηση στοιχείων',
                'is_active': True
            },
            {
                'code': 'Secretary_KEDASY',
                'name': 'Secretary',
                'description': 'Γραμματέας - διαχείριση πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ',
                'is_active': True
            }
        ]
        
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                code=role_data['code'],
                defaults={
                    'name': role_data['name'],
                    'description': role_data['description'],
                    'is_active': role_data['is_active']
                }
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε ρόλος: {role.name} ({role.code})')
            else:
                self.stdout.write(f'  Ρόλος υπάρχει ήδη: {role.name} ({role.code})')
    def load_department_types(self):
        """Φόρτωση τύπων τμημάτων"""
        self.stdout.write('Φόρτωση τύπων τμημάτων...')
        
        department_types_data = [
            {
                'code': 'PDEDE',
                'name': 'ΠΔΕΔΕ',
                'description': 'Περιφερειακή Διεύθυνση Εκπαίδευσης',
                'is_active': True
            },
            {
                'code': 'DEPARTMENT',
                'name': 'Τμήμα',
                'description': 'Αυτόματα δημιουργημένος τύπος: Τμήμα',
                'is_active': True
            },
            {
                'code': 'DIRECTION',
                'name': 'Διεύθυνση',
                'description': 'Αυτόματα δημιουργημένος τύπος: Διεύθυνση',
                'is_active': True
            },
            {
                'code': 'KEDASY',
                'name': 'ΚΕΔΑΣΥ',
                'description': '',
                'is_active': True
            },
            {
                'code': 'KEPEA',
                'name': 'ΚΕΠΕΑ',
                'description': '',
                'is_active': True
            },
            {
                'code': 'TMIMA_PDEDE',
                'name': 'Τμήμα ΠΔΕΔΕ',
                'description': 'Τμήματα της ΠΔΕΔΕ (Α, Β, Γ, Δ, Νομική Υποστήριξη)',
                'is_active': True
            },
            {
                'code': 'SDEI',
                'name': 'ΣΔΕΥ',
                'description': 'ΣΔΕΥ',
                'is_active': True
            },
            {
                'code': 'KFP',
                'name': 'ΚΠΦ',
                'description': 'ΚΕΝΤΡΑ ΦΙΛΟΞΕΝΕΙΑΣ ΠΡΟΣΦΥΓΩΝ',
                'is_active': True
            }
        ]
        
        for dept_type_data in department_types_data:
            dept_type, created = DepartmentType.objects.get_or_create(
                code=dept_type_data['code'],
                defaults={
                    'name': dept_type_data['name'],
                    'description': dept_type_data['description'],
                    'is_active': dept_type_data['is_active']
                }
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε τύπος τμήματος: {dept_type.name} ({dept_type.code})')
            else:
                self.stdout.write(f'  Τύπος τμήματος υπάρχει ήδη: {dept_type.name} ({dept_type.code})')
    def load_departments(self):
        """Φόρτωση τμημάτων"""
        self.stdout.write('Φόρτωση τμημάτων...')
        
        # Βρίσκω τα απαραίτητα objects
        try:
            # Prefectures
            achaia = Prefecture.objects.get(code='ACH')
            aitolia = Prefecture.objects.get(code='AIT')
            hleia = Prefecture.objects.get(code='HLE')
            
            # Headquarters
            patra = Headquarters.objects.get(code='PATRA')
            mesolongi = Headquarters.objects.get(code='MESOLONGI')
            pyrgos = Headquarters.objects.get(code='PYRGOS')
            kleitoria = Headquarters.objects.get(code='KLEITORIA')
            krestena = Headquarters.objects.get(code='KRESTENA')
            andravida = Headquarters.objects.get(code='ANDRAVIDA')
            
            # Department Types
            pdede_type = DepartmentType.objects.get(code='PDEDE')
            direction_type = DepartmentType.objects.get(code='DIRECTION')
            department_type = DepartmentType.objects.get(code='DEPARTMENT')
            kedasy_type = DepartmentType.objects.get(code='KEDASY')
            kepea_type = DepartmentType.objects.get(code='KEPEA')
            sdei_type = DepartmentType.objects.get(code='SDEI')
            kfp_type = DepartmentType.objects.get(code='KFP')
            tmima_pdede_type = DepartmentType.objects.get(code='TMIMA_PDEDE')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Σφάλμα κατά τη φόρτωση dependencies: {e}'))
            return
        
        # 1. ΠΔΕΔΕ - Κεντρική Διεύθυνση
        pdede, created = Department.objects.get_or_create(
            code='PDEDE',
            defaults={
                'name': 'Περιφερειακή Διεύθυνση Εκπαίδευσης Δυτικής Ελλάδας',
                'department_type': pdede_type,
                'prefecture': achaia,
                'headquarters': patra,
                'parent_department': None,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Δημιουργήθηκε: {pdede.name}')
        
        # 2. ΑΥΤΟΤΕΛΗΣ ΔΙΕΥΘΥΝΣΗ - κάτω από την ΠΔΕΔΕ
        autotelous_dn, created = Department.objects.get_or_create(
            code='AUTOTELOUS_DN',
            defaults={
                'name': 'Αυτοτελής Διεύθυνση Διοικητικής, Οικονομικής και Παιδαγωγικής Υποστήριξης',
                'department_type': direction_type,
                'prefecture': achaia,
                'headquarters': patra,
                'parent_department': pdede,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Δημιουργήθηκε: {autotelous_dn.name}')
        
        # 3. Τμήματα κάτω από την ΑΥΤΟΤΕΛΗΣ ΔΙΕΥΘΥΝΣΗ
        tmimata_pdede = [
            ('TMIMA_A', 'Τμήμα Α'),
            ('TMIMA_B', 'Τμήμα Β'),
            ('TMIMA_G', 'Τμήμα Γ'),
            ('TMIMA_D', 'Τμήμα Δ'),
            ('NOMIKI_YPOSTIRIXI', 'Γραφείο Νομικής Υποστήριξης'),
        ]
        
        for code, name in tmimata_pdede:
            dept, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': tmima_pdede_type,
                    'prefecture': achaia,
                    'headquarters': patra,
                    'parent_department': autotelous_dn,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε: {dept.name}')
        
        # 4. ΚΕΔΑΣΥ - κάτω από την ΠΔΕΔΕ
        kedasy_data = [
            ('KEDASY_1_PATRAS', 'ΚΕ.Δ.Α.Σ.Υ. 1ο ΠΑΤΡΑΣ', patra, achaia),
            ('KEDASY_2_PATRAS', 'ΚΕ.Δ.Α.Σ.Υ. 2ο ΠΑΤΡΑΣ', patra, achaia),
            ('KEDASY_AITOLIAS', 'ΚΕ.Δ.Α.Σ.Υ. ΑΙΤΩΛΟΑΚΑΡΝΑΝΙΑΣ', mesolongi, aitolia),
            ('KEDASY_HLEIAS', 'ΚΕ.Δ.Α.Σ.Υ. ΗΛΕΙΑΣ', pyrgos, hleia),
        ]
        
        for code, name, hq, prefecture in kedasy_data:
            kedasy, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': kedasy_type,
                    'prefecture': prefecture,
                    'headquarters': hq,
                    'parent_department': pdede,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε: {kedasy.name}')
        
        # 5. ΚΕΠΕΑ - κάτω από την ΠΔΕΔΕ
        kepea_data = [
            ('KEPEA_ACHAIAS', 'ΚΕΠΕΑ ΑΧΑΪΑΣ', kleitoria, achaia),
            ('KEPEA_HLEIAS', 'ΚΕΠΕΑ ΗΛΕΙΑΣ', krestena, hleia),
            ('KEPEA_AITOLIAS', 'ΚΕΠΕΑ ΑΙΤΩΛΟΑΚΑΡΝΑΝΙΑΣ', mesolongi, aitolia),
        ]
        
        for code, name, hq, prefecture in kepea_data:
            kepea, created = Department.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'department_type': kepea_type,
                    'prefecture': prefecture,
                    'headquarters': hq,
                    'parent_department': pdede,
                    'is_active': True
                }
            )
            if created:
                self.stdout.write(f'  Δημιουργήθηκε: {kepea.name}')
        
        # 6. ΚΕΝΤΡΟ ΦΙΛΟΞΕΝΙΑΣ ΠΡΟΣΦΥΓΩΝ
        kfp, created = Department.objects.get_or_create(
            code='KFP_ANDRAVIDAS',
            defaults={
                'name': 'Κέντρο Φιλοξενίας Προσφύγων - Ανδραβίδας-Κυλλήνης',
                'department_type': kfp_type,
                'prefecture': hleia,
                'headquarters': andravida,
                'parent_department': pdede,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Δημιουργήθηκε: {kfp.name}')
        
        # 7. ΔΝ/ΤΕΣ ΕΚΠΑΙΔΕΥΣΗΣ
        dntes, created = Department.objects.get_or_create(
            code='DNTES_EKPAIDEUSIS',
            defaults={
                'name': 'ΔΝ/ΤΕΣ Εκπαίδευσης',
                'department_type': department_type,
                'prefecture': achaia,
                'headquarters': patra,
                'parent_department': pdede,
                'is_active': True
            }
        )
        if created:
            self.stdout.write(f'  Δημιουργήθηκε: {dntes.name}')
        
        # 8. ΣΔΕΥ - κάτω από κάθε ΚΕΔΑΣΥ (εικονικά τμήματα)
        self.load_sdei_departments()
        
        self.stdout.write('Ολοκλήρωση φόρτωσης τμημάτων.')
    
    def load_sdei_departments(self):
        """Φόρτωση ΣΔΕΥ (εικονικά τμήματα)"""
        self.stdout.write('Φόρτωση ΣΔΕΥ...')
        
        try:
            # Βρίσκω τα ΚΕΔΑΣΥ
            kedasy_1_patras = Department.objects.get(code='KEDASY_1_PATRAS')
            kedasy_2_patras = Department.objects.get(code='KEDASY_2_PATRAS')
            kedasy_aitolias = Department.objects.get(code='KEDASY_AITOLIAS')
            kedasy_hleias = Department.objects.get(code='KEDASY_HLEIAS')
            
            # Prefectures
            achaia = Prefecture.objects.get(code='ACH')
            aitolia = Prefecture.objects.get(code='AIT')
            hleia = Prefecture.objects.get(code='HLE')
            
            # Headquarters
            patra = Headquarters.objects.get(code='PATRA')
            mesolongi = Headquarters.objects.get(code='MESOLONGI')
            pyrgos = Headquarters.objects.get(code='PYRGOS')
            
            # Department Type
            sdei_type = DepartmentType.objects.get(code='SDEI')
            
            # ΣΔΕΥ κάτω από ΚΕΔΑΣΥ 1ο ΠΑΤΡΑΣ
            sdei_kedasy_1_data = [
                ('SDEI_1_EIDIKO_AIGIOU', 'Σ.Δ.Ε.Υ. 1ο ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΑΙΓΙΟΥ'),
                ('SDEI_EIDIKO_NIPIAGOGEIOU_AIGIOU', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΑΙΓΙΟΥ'),
                ('SDEI_EEEEK_AIGIOU', 'Σ.Δ.Ε.Υ. Ε.Ε.Ε.ΕΚ ΑΙΓΙΟΥ'),
                ('SDEI_EIDIKO_KALAVRYTON', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΚΑΛΑΒΡΥΤΩΝ'),
                ('SDEI_2_EIDIKO_PATRON', 'Σ.Δ.Ε.Υ. 2ο ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΠΑΤΡΩΝ'),
                ('SDEI_EIDIKO_KOFON_PATRON', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΚΩΦΩΝ-ΒΑΡΗΚΟΩΝ ΠΑΤΡΑΣ'),
                ('SDEI_EEEEK_ACHAIAS', 'Σ.Δ.Ε.Υ. Ε.Ε.Ε.Ε.Κ. ΑΧΑΪΑΣ'),
                ('SDEI_2_NIPIAGOGEIOU_PATRON', 'Σ.Δ.Ε.Υ. 2ο ΕΙΔΙΚΟ ΝΗΠΙΑΓΩΓΕΙΟ ΠΑΤΡΑΣ'),
                ('SDEI_NIPIAGOGEIOU_KOFON_PATRON', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΚΩΦΩΝ ΠΑΤΡΩΝ'),
                ('SDEI_48_DIMOTIKO_PATRON', 'Σ.Δ.Ε.Υ. 48ου ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΩΝ'),
            ]
            
            for code, name in sdei_kedasy_1_data:
                sdei, created = Department.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'department_type': sdei_type,
                        'prefecture': achaia,
                        'headquarters': patra,
                        'parent_department': kedasy_1_patras,
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(f'  Δημιουργήθηκε: {sdei.name}')
            
            # ΣΔΕΥ κάτω από ΚΕΔΑΣΥ 2ο ΠΑΤΡΑΣ
            sdei_kedasy_2_data = [
                ('SDEI_EIDIKO_KATO_ACHAIAS', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΚΑΤΩ ΑΧΑΙΑΣ'),
                ('SDEI_44_DIMOTIKO_PATRON', 'Σ.Δ.Ε.Υ. 44ο ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΠΑΤΡΩΝ (ΕΙΔΙΚΟ ΝΗΠΙΑΓΩΓΕΙΟ ΚΑΤΩ ΑΧΑΙΑΣ)'),
                ('SDEI_1_EIDIKO_PATRON', 'Σ.Δ.Ε.Υ. 1ΟΥ ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΩΝ'),
                ('SDEI_3_EIDIKO_PATRON_PIKPA', 'Σ.Δ.Ε.Υ. 3οΥ ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΩΝ - ΠΙΚΠΑ'),
                ('SDEI_4_EIDIKO_PATRON_AUTISM', 'Σ.Δ.Ε.Υ. 4ΟΥ ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΑΣ - ΕΙΔΙΚΟ ΦΑΣΜΑΤΟΣ ΑΥΤΙΣΜΟΥ'),
                ('SDEI_ENEEGY_PATRON', 'Σ.Δ.Ε.Υ. ΕΝ.Ε.Ε.ΓΥ.- Λ. ΠΑΤΡΩΝ'),
                ('SDEI_1_NIPIAGOGEIOU_PATRON', 'Σ.Δ.Ε.Υ. 1ου ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΠΑΤΡΑΣ'),
                ('SDEI_3_NIPIAGOGEIOU_PATRON', 'Σ.Δ.Ε.Υ. 3ου ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΠΑΤΡΩΝ'),
                ('SDEI_39_DIMOTIKO_PATRON', 'Σ.Δ.Ε.Υ. 39ου ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΩΝ'),
                ('SDEI_61_DIMOTIKO_PATRON', 'Σ.Δ.Ε.Υ. 61ο ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΑΤΡΩΝ'),
            ]
            
            for code, name in sdei_kedasy_2_data:
                sdei, created = Department.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'department_type': sdei_type,
                        'prefecture': achaia,
                        'headquarters': patra,
                        'parent_department': kedasy_2_patras,
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(f'  Δημιουργήθηκε: {sdei.name}')
            
            # ΣΔΕΥ κάτω από ΚΕΔΑΣΥ ΑΙΤΩΛΟΑΚΑΡΝΑΝΙΑΣ
            sdei_aitolias_data = [
                ('SDEI_1_EIDIKO_AGRINIOU', 'Σ.Δ.Ε.Υ. 1ΟΥ ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΑΓΡΙΝΙΟΥ'),
                ('SDEI_2_EIDIKO_AGRINIOU', 'Σ.Δ.Ε.Υ. 2ΟΥ ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟY ΣΧΟΛΕΙΟΥ ΑΓΡΙΝΙΟΥ'),
                ('SDEI_EIDIKO_AGRINIOU_MARIA', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΑΓΡΙΝΙΟΥ "ΜΑΡΙΑ ΔΗΜΑΔΗ"'),
                ('SDEI_NIPIAGOGEIOU_AGRINIOU_MARIA', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΑΓΡΙΝΙΟΥ "ΜΑΡΙΑ ΔΗΜΑΔΗ"'),
                ('SDEI_ENIAIO_AGRINIOU', 'Σ.Δ.Ε.Υ. ΕΝΙΑΙΟ ΕΙΔΙΚΟ ΕΠΑΓΓΕΛΜΑΤΙΚΟ ΓΥΜΝΑΣΙΟ - ΛΥΚΕΙΟ ΑΓΡΙΝΙΟΥ'),
                ('SDEI_EIDIKO_VONITSAS', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΒΟΝΙΤΣΑΣ'),
                ('SDEI_EIDIKO_MESOLONGIOU', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΜΕΣΟΛΟΓΓΙΟΥ'),
                ('SDEI_NIPIAGOGEIOU_MESOLONGIOU', 'ΕΙΔΙΚΟ ΝΗΠΙΑΓΩΓΕΙΟ ΜΕΣΟΛΟΓΓΙΟΥ'),
                ('SDEI_ENIAIO_MESOLONGIOU', 'Σ.Δ.Ε.Υ. ΕΝΙΑΙΟΥ ΕΙΔΙΚΟΥ ΕΠΑΓΓΕΛΜΑΤΙΚΟΥ ΓΥΜΝΑΣΙΟΥ - ΛΥΚΕΙΟΥ ΜΕΣΟΛΟΓΓΙΟΥ'),
                ('SDEI_EIDIKO_NAFPAKTOU', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟ ΝΑΥΠΑΚΤΟΥ'),
                ('SDEI_EEEEK_NAFPAKTOU', 'ΕΕΕΕΚ ΝΑΥΠΑΚΤΟΣ – ΕΕΕΕΚ'),
            ]
            
            for code, name in sdei_aitolias_data:
                sdei, created = Department.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'department_type': sdei_type,
                        'prefecture': aitolia,
                        'headquarters': mesolongi,
                        'parent_department': kedasy_aitolias,
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(f'  Δημιουργήθηκε: {sdei.name}')
            
            # ΣΔΕΥ κάτω από ΚΕΔΑΣΥ ΗΛΕΙΑΣ
            sdei_hleias_data = [
                ('SDEI_EIDIKO_LECHAINON', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΛΕΧΑΙΝΩΝ'),
                ('SDEI_DIMOTIKO_KRESTENON', 'Σ.Δ.Ε.Υ. ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΚΡΕΣΤΕΝΩΝ (ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΚΡΕΣΤΕΝΩΝ)'),
                ('SDEI_NIPIAGOGEIOU_PINEIOU', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟ ΝΗΠΙΑΓΩΓΕΙΟ ΠΗΝΕΙΟΥ'),
                ('SDEI_NIPIAGOGEIOU_PYRGOU', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΝΗΠΙΑΓΩΓΕΙΟΥ ΠΥΡΓΟΥ'),
                ('SDEI_EIDIKO_PYRGOU', 'Σ.Δ.Ε.Υ. ΕΙΔΙΚΟΥ ΔΗΜΟΤΙΚΟΥ ΣΧΟΛΕΙΟΥ ΠΥΡΓΟΥ'),
                ('SDEI_FOUFEIO_AMALIAD', 'Σ.Δ.Ε.Υ. 4/Θ ΦΟΥΦΕΙΟ ΕΙΔΙΚΟ ΔΗΜΟΤΙΚΟ ΣΧΟΛΕΙΟ ΑΜΑΛΙΑΔΑΣ'),
                ('SDEI_ENIAIO_PYRGOU', 'Σ.Δ.Ε.Υ. ΕΝΙΑΙΟΥ ΕΙΔΙΚΟΥ ΕΠΑΓΓΕΛΜΑΤΙΚΟΥ ΓΥΜΝΑΣΙΟΥ-ΛΥΚΕΙΟΥ ΠΥΡΓΟΥ'),
                ('SDEI_EEEEK_PYRGOU', 'Σ.Δ.Ε.Υ. Ε.Ε.Ε.Ε.Κ. ΠΥΡΓΟΥ ΗΛΕΙΑΣ'),
            ]
            
            for code, name in sdei_hleias_data:
                sdei, created = Department.objects.get_or_create(
                    code=code,
                    defaults={
                        'name': name,
                        'department_type': sdei_type,
                        'prefecture': hleia,
                        'headquarters': pyrgos,
                        'parent_department': kedasy_hleias,
                        'is_active': True
                    }
                )
                if created:
                    self.stdout.write(f'  Δημιουργήθηκε: {sdei.name}')
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Σφάλμα κατά τη φόρτωση ΣΔΕΥ: {e}'))
        
        self.stdout.write('Ολοκλήρωση φόρτωσης ΣΔΕΥ.')