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
                'name': '1 Κανονική Άδεια',
                'description': 'Κανονική Άδεια',
                'subject_text': 'Χορήγηση κανονικής άδειας',
                'decision_text': 'κανονική άδεια',
                'folder': 'Φ 12.1/',
                'general_category': 'Κανονικές Άδειες',
                'max_days': 25,
                'requires_approval': True
            },
            {
                'name': '2α Αναρρωτική Άδεια με ΥΔ',
                'description': 'Αναρρωτική Άδεια με ΥΔ',
                'subject_text': 'Χορήγηση αναρρωτικής άδειας',
                'decision_text': 'αναρρωτική άδεια',
                'folder': 'Φ 12.2/',
                'general_category': 'Αναρρωτικές Άδειες',
                'max_days': 15,
                'requires_approval': True
            },
            {
                'name': '3 Άδεια αιμοδοσίας',
                'description': 'Άδεια αιμοδοσίας',
                'subject_text': 'Χορήγηση άδειας αιμοδοσίας',
                'decision_text': 'άδεια αιμοδοσίας',
                'folder': 'Φ 12.4/',
                'general_category': 'Άδειες Αιμοδοσίας',
                'max_days': 2,
                'requires_approval': True
            },
            {
                'name': 'Συνδικαλιστική Άδεια',
                'description': 'Συνδικαλιστική Άδεια',
                'subject_text': 'Χορήγηση συνδικαλιστικής άδεια',
                'decision_text': 'συνδικαλιστική άδεια',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 10,
                'requires_approval': True
            },
            {
                'name': '4 Άδεια για την παρακολούθηση της σχολικής επίδοσης των τέκνων',
                'description': 'Άδεια για την παρακολούθηση της σχολικής επίδοσης των τέκνων',
                'subject_text': 'Χορήγηση άδειας για την παρακολούθηση της σχολικής επίδοσης των τέκνων',
                'decision_text': 'άδεια για την παρακολούθηση της σχολικής επίδοσης των τέκνων',
                'folder': 'Φ 12.3/',
                'general_category': 'Γονικές Άδειες',
                'max_days': 4,
                'requires_approval': True
            },
            {
                'name': '5 Άδεια για επιμορφωτικούς ή επιστημονικούς λόγους',
                'description': 'Άδεια για επιμορφωτικούς ή επιστημονικούς λόγους',
                'subject_text': 'Χορήγηση άδειας για επιμορφωτικούς ή επιστημονικούς λόγους',
                'decision_text': 'άδεια για επιμορφωτικούς ή επιστημονικούς λόγους',
                'folder': 'Φ 12.6/',
                'general_category': 'Επιμορφωτικές Άδειες',
                'max_days': 30,
                'requires_approval': True
            },
            {
                'name': 'Άδεια Γάμου',
                'description': 'Άδεια Γάμου',
                'subject_text': 'Χορήγηση άδειας γάμου',
                'decision_text': 'άδεια γάμου',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 5,
                'requires_approval': True
            },
            {
                'name': 'Ειδική άδεια(θανάτου)',
                'description': 'θανάτου',
                'subject_text': 'Χορήγηση Ειδικής άδειας λόγω θανάτου συγγενούς',
                'decision_text': 'ειδική άδεια λόγω θανάτου συγγενούς',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 3,
                'requires_approval': True
            },
            {
                'name': 'Άδεια Γέννησης Τέκνου',
                'description': 'Άδεια Γέννησης Τέκνου',
                'subject_text': 'Χορήγηση άδειας γέννησης τέκνου',
                'decision_text': 'άδεια γέννησης τέκνου',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 2,
                'requires_approval': True
            },
            {
                'name': 'Άδεια άσκησης εκλογικού δικαιώματος',
                'description': 'Άδεια άσκησης εκλογικού δικαιώματος',
                'subject_text': 'Χορήγηση άδειας άσκησης εκλογικού δικαιώματος',
                'decision_text': 'άδεια άσκησης εκλογικού δικαιώματος',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 1,
                'requires_approval': True
            },
            {
                'name': 'Άδεια για συμμετοχή σε δίκη',
                'description': 'Άδεια για συμμετοχή σε δίκη',
                'subject_text': 'Χορήγηση άδειας για συμμετοχή σε δίκη',
                'decision_text': 'άδεια για συμμετοχή σε δίκη',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 2,
                'requires_approval': True
            },
            {
                'name': 'Άδεια νοσήματος',
                'description': 'Άδεια νοσήματος',
                'subject_text': 'Χορήγηση άδειας νοσήματος',
                'decision_text': 'άδεια νοσήματος',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 30,
                'requires_approval': True
            },
            {
                'name': 'Άδεια αναπηρίας',
                'description': 'Άδεια αναπηρίας',
                'subject_text': 'Χορήγηση άδειας αναπηρίας',
                'decision_text': 'άδεια αναπηρίας',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 10,
                'requires_approval': True
            },
            {
                'name': 'Άδεια αιρετών ΟΤΑ Α\' & Β΄ βαθμού',
                'description': 'Άδεια αιρετών ΟΤΑ Α\' & Β΄ βαθμού',
                'subject_text': 'Χορήγηση άδειας αιρετών ΟΤΑ Α\' & Β΄ βαθμού',
                'decision_text': 'άδεια αιρετών ΟΤΑ Α\' & Β΄ βαθμού',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 20,
                'requires_approval': True
            },
            {
                'name': 'Άδεια κύησης',
                'description': 'Άδεια κύησης',
                'subject_text': 'Χορήγηση άδειας κύησης',
                'decision_text': 'άδεια κύησης',
                'folder': 'Φ 12.5/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 60,
                'requires_approval': True
            },
            {
                'name': 'Άδεια εξετάσεων',
                'description': 'Άδεια εξετάσεων',
                'subject_text': 'Χορήγηση άδειας εξετάσεων',
                'decision_text': 'άδεια εξετάσεων',
                'folder': 'Φ 12.6/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 14,
                'requires_approval': True
            },
            {
                'name': 'Άδεια χωρίς αποδοχές',
                'description': 'Άδεια χωρίς αποδοχές',
                'subject_text': 'Χορήγηση άδειας χωρίς αποδοχές',
                'decision_text': 'άδεια χωρίς αποδοχές',
                'folder': 'Φ 12.8/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 365,
                'requires_approval': True
            },
            {
                'name': '2β Αναρρωτική Άδεια με Ιατρική Γνωμάτευση',
                'description': 'Αναρρωτική Άδεια με Ιατρική Γνωμάτευση',
                'subject_text': 'Χορήγηση αναρρωτικής άδειας',
                'decision_text': 'αναρρωτική άδεια',
                'folder': 'Φ 12.2/',
                'general_category': 'Αναρρωτικές Άδειες',
                'max_days': 20,
                'requires_approval': True
            },
            {
                'name': '2γ Αναρρωτική Άδεια με απόφ. Υγειονομικής Επιτροπής',
                'description': 'Αναρρωτική Άδεια με απόφ. Υγειονομικής Επιτροπής',
                'subject_text': 'Χορήγηση αναρρωτικής άδειας',
                'decision_text': 'αναρρωτική άδεια',
                'folder': 'Φ 12.2/',
                'general_category': 'Αναρρωτικές Άδειες',
                'max_days': 30,
                'requires_approval': True
            },
            {
                'name': 'Εορταστική Άδεια',
                'description': 'Εορταστική Άδεια',
                'subject_text': 'Χορήγηση εορταστικής άδειας',
                'decision_text': 'εορταστική άδεια',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 2,
                'requires_approval': True
            },
            {
                'name': 'Άδεια λοχείας',
                'description': 'Άδεια λοχείας',
                'subject_text': 'Χορήγηση άδειας λοχείας',
                'decision_text': 'άδεια λοχείας',
                'folder': 'Φ 12.5/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 60,
                'requires_approval': True
            },
            {
                'name': 'Άδεια ανατροφής τέκνου',
                'description': 'Άδεια ανατροφής τέκνου',
                'subject_text': 'Χορήγηση Άδειας ανατροφής τέκνου',
                'decision_text': 'άδεια ανατροφής τέκνου',
                'folder': 'Φ 12.5/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 120,
                'requires_approval': True
            },
            {
                'name': 'Άδεια ασθένειας τέκνων',
                'description': 'Άδεια ασθένειας τέκνων',
                'subject_text': 'Χορήγηση άδειας ασθένειας τέκνων',
                'decision_text': 'άδεια ασθένειας τέκνων',
                'folder': 'Φ 12.2/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 14,
                'requires_approval': True
            },
            {
                'name': 'Άδεια νοσήματος τέκνου',
                'description': 'Άδεια νοσήματος τέκνου',
                'subject_text': 'Χορήγηση άδειας νοσήματος τέκνου',
                'decision_text': 'άδεια νοσήματος τέκνου',
                'folder': 'Φ.12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 30,
                'requires_approval': True
            },
            {
                'name': 'Άδεια Αναπηρίας',
                'description': 'Άδεια Αναπηρίας',
                'subject_text': 'Χορήγηση άδειας αναπηρίας',
                'decision_text': 'άδεια αναπηρίας',
                'folder': 'Φ.12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 10,
                'requires_approval': True
            },
            {
                'name': 'Άδεια ειδικού σκοπού',
                'description': 'Άδεια ειδικού σκοπού',
                'subject_text': 'Χορήγηση άδειας ειδικού σκοπού',
                'decision_text': 'άδεια ειδικού σκοπου',
                'folder': 'Φ.12.10/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 5,
                'requires_approval': True
            },
            {
                'name': 'Αναρρωτική άδεια ειδικού σκοπού',
                'description': 'Αναρρωτική άδεια ειδικού σκοπού',
                'subject_text': 'Χορήγηση αναρρωτικής άδεια ειδικού σκοπού',
                'decision_text': 'αναρρωτική άδεια ειδικού σκοπού',
                'folder': 'Φ.12.10/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 10,
                'requires_approval': True
            },
            {
                'name': 'Άδεια γυναικολογικού ελέγχου',
                'description': 'Άδεια γυναικολογικού ελέγχου',
                'subject_text': 'Χορήγηση άδειας γυναικολογικού ελέγχου',
                'decision_text': 'άδεια γυναικολογικού ελέγχου',
                'folder': 'Φ.12.11/',
                'general_category': 'Αναρρωτικές Άδειες',
                'max_days': 1,
                'requires_approval': True
            },
            {
                'name': 'Ειδική άδεια απουσίας ομάδων αυξημένου κινδύνου',
                'description': 'Ειδική άδεια απουσίας ομάδων αυξημένου κινδύνου',
                'subject_text': 'Χορήγηση ειδικής άδειας απουσίας ομάδων αυξημένου κινδύνου',
                'decision_text': 'ειδική άδεια απουσίας ομάδων αυξημένου κινδύνου',
                'folder': 'Φ.12.11/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 30,
                'requires_approval': True
            },
            {
                'name': 'Μονογονεϊκή Άδεια',
                'description': 'Μονογονεϊκή Άδεια',
                'subject_text': 'Χορήγηση Μονογονεϊκής Άδειας',
                'decision_text': 'μονογονεϊκή άδεια',
                'folder': 'Φ 12.4/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 6,
                'requires_approval': True
            },
            {
                'name': 'Άδεια ειδικού σκοπού λόγω νόσησης τέκνου με κορωνοϊό COVID-19',
                'description': 'Άδεια ειδικού σκοπού λόγω νόσησης τέκνου με κορωνοϊό COVID-19',
                'subject_text': 'Χορήγηση άδειας ειδικού σκοπού λόγω νόσησης τέκνου με κορωνοϊό COVID-19',
                'decision_text': 'άδεια ειδικού σκοπού λόγω νόσησης τέκνου με κορωνοϊό COVID-19',
                'folder': 'Φ 12.10/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 14,
                'requires_approval': True
            },
            {
                'name': 'Άδεια προγεννητικού ελέγχου',
                'description': 'Άδεια προγεννητικού ελέγχου',
                'subject_text': 'Χορήγηση άδειας προγεννητικού ελέγχου',
                'decision_text': 'άδεια προγεννητικού ελέγχου',
                'folder': 'Φ 12.5/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 7,
                'requires_approval': True
            },
            {
                'name': 'Γονική Άδεια (Ν.4808/2021)',
                'description': 'Γονική Άδεια (Ν.4808/2021)',
                'subject_text': 'Χορήγηση Γονικής Άδειας (Ν.4808/2021)',
                'decision_text': 'Γονική Άδεια (Ν.4808/2021)',
                'folder': 'Φ 12.5/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 120,
                'requires_approval': True
            },
            {
                'name': 'Πατρότητας',
                'description': 'Πατρότητας (Ν.4808/2021)',
                'subject_text': 'Χορήγηση Άδειας Πατρότητας (Ν.4808/2021)',
                'decision_text': 'Άδεια Πατρότητας (Ν.4808/2021)',
                'folder': 'Φ 12.5/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 14,
                'requires_approval': True
            },
            {
                'name': 'Υποβολής σε ιατρικές μεθόδους υποβοηθούμενης αναπαραγωγής',
                'description': 'Υποβολής σε ιατρικές μεθόδους υποβοηθούμενης αναπαραγωγής',
                'subject_text': 'Χορήγηση άδειας Υποβολής σε ιατρικές μεθόδους υποβοηθούμενης αναπαραγωγής',
                'decision_text': 'άδεια Υποβολής σε ιατρικές μεθόδους υποβοηθούμενης αναπραγωγής',
                'folder': 'Φ 12.5/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 7,
                'requires_approval': True
            },
            {
                'name': 'Ειδική άδεια διευκόλυνσης',
                'description': 'Ειδική άδεια διευκόλυνσης',
                'subject_text': 'Χορήγηση Ειδικής άδειας διευκόλυνσης',
                'decision_text': 'υποψήφιο αιρετό εκπρόσωπο για το Περιφερειακό Υπηρεσιακό Συμβούλιο Διοικητικού Προσωπικού (ΠΥΣΔΥΠ) Δυτικής Ελλάδας, άδεια ειδική διευκόλυνσης',
                'folder': 'Φ 12.5/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 5,
                'requires_approval': True
            },
            {
                'name': 'Ειδική άδεια ανυπαίτιου κωλύματος',
                'description': 'Ειδική άδεια ανυπαίτιου κωλύματος',
                'subject_text': 'Χορήγηση ειδικής άδειας ανυπαίτιου κωλύματος',
                'decision_text': 'ειδική άδεια ανυπαίτιου κωλύματος',
                'folder': 'Φ 12.5/',
                'general_category': 'Άλλες Άδειες',
                'max_days': 5,
                'requires_approval': True
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
                        'subject_text': leave_type_data.get('subject_text', ''),
                        'decision_text': leave_type_data.get('decision_text', ''),
                        'folder': leave_type_data.get('folder', ''),
                        'general_category': leave_type_data.get('general_category', ''),
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
                        'subject_text': leave_type_data.get('subject_text', ''),
                        'decision_text': leave_type_data.get('decision_text', ''),
                        'folder': leave_type_data.get('folder', ''),
                        'general_category': leave_type_data.get('general_category', ''),
                        'is_active': True
                    }
                )
                action = 'Δημιουργήθηκε' if created else 'Υπάρχει ήδη'
            
            self.stdout.write(f'  {action}: {leave_type.name}')
