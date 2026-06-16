import os
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation
from notifications.models import Notification
from accounts.department_utils import is_sdey_department, is_sdey_under_kedasy

User = get_user_model()


class LeaveType(models.Model):
    """Τύπος άδειας"""
    code = models.CharField('Κωδικός', max_length=50, unique=True, blank=True,
                            help_text='Προγραμματικός κωδικός (π.χ. ANNUAL, SICK, BLOOD)')
    name = models.CharField('Όνομα Τύπου', max_length=100)
    max_days = models.PositiveIntegerField('Μέγιστες Ημέρες', null=True, blank=True)
    requires_approval = models.BooleanField('Απαιτεί Έγκριση από Προϊστάμενο', default=True)
    is_active = models.BooleanField('Ενεργός', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    subject_text = models.TextField('Κείμενο Θέματος', blank=True)
    decision_text = models.TextField('Κείμενο Απόφασης', blank=True)
    affects_regular_leave_balance = models.BooleanField('Επηρεάζει Υπόλοιπο Κανονικών', default=True,
        help_text='Αν είναι ενεργό, η ολοκλήρωση αυτής της άδειας δημιουργεί εγγραφή στο ιστορικό υπολοίπου')
    is_simple = models.BooleanField('Απλή Άδεια', default=False,
        help_text='Για εορταστικές/προφορικές/επιμορφωτικές άδειες')
    workflow_variant = models.CharField('Workflow Variant', max_length=30, default='STANDARD',
        help_text='STANDARD, KEDASY, SDEY - καθορίζει το approval path και τα rules')
    is_sick_leave_yd = models.BooleanField('Αναρρωτική Άδεια με ΥΔ', default=False,
        help_text='Αν είναι ενεργό, μετράει στο ετήσιο όριο αναρρωτικών με ΥΔ (2/έτος)')
    is_sick_leave_total = models.BooleanField('Σύνολο Αναρρωτικών', default=False,
        help_text='Αν είναι ενεργό, οι ημέρες μετράνε στο σύνολο αναρρωτικών του έτους (για alert Υγειονομικής Επιτροπής)')
    instructions = models.TextField('Οδηγίες', blank=True,
        help_text='Οδηγίες που εμφανίζονται στον αιτούντα κατά τη δημιουργία αίτησης')
    is_revocation = models.BooleanField('Ανάκληση', default=False,
        help_text='Αν είναι ενεργό, ο τύπος άδειας αφορά ανάκληση άδειας')
    
    class Meta:
        verbose_name = 'Τύπος Άδειας'
        verbose_name_plural = 'Τύποι Αδειών'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def has_instructions(self):
        """Εμφάνιση στο admin αν υπάρχουν οδηγίες"""
        return bool(self.instructions)
    has_instructions.short_description = 'Οδηγίες'
    has_instructions.boolean = True


class LeavePeriod(models.Model):
    """Διάστημα άδειας - ένα τμήμα μιας αίτησης άδειας"""
    
    leave_request = models.ForeignKey('LeaveRequest', on_delete=models.CASCADE, related_name='periods', verbose_name='Αίτηση Άδειας')
    start_date = models.DateField('Ημερομηνία Έναρξης')
    end_date = models.DateField('Ημερομηνία Λήξης')
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Διάστημα Άδειας'
        verbose_name_plural = 'Διαστήματα Αδειών'
        ordering = ['start_date']
    
    def __str__(self):
        return f"{self.start_date} - {self.end_date} ({self.days} ημέρες)"
    
    @property
    def days(self):
        """Υπολογισμός ημερών του διαστήματος"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0
    
    def clean(self):
        """Επικύρωση δεδομένων"""
        from django.core.exceptions import ValidationError
        
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError('Η ημερομηνία έναρξης δεν μπορεί να είναι μεταγενέστερη της ημερομηνίας λήξης.')
            
            # Έλεγχος για επικάλυψη με άλλα διαστήματα της ίδιας αίτησης
            if self.leave_request_id:
                overlapping = LeavePeriod.objects.filter(
                    leave_request=self.leave_request
                ).exclude(pk=self.pk).filter(
                    start_date__lte=self.end_date,
                    end_date__gte=self.start_date
                )
                if overlapping.exists():
                    raise ValidationError('Το διάστημα επικαλύπτεται με άλλο διάστημα της ίδιας αίτησης.')


def secure_file_path(instance, filename):
    """Δημιουργία ασφαλούς path για αρχείο"""
    # Δημιουργία UUID για το αρχείο
    ext = filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{ext}"
    
    # Δημιουργία path με το ID της αίτησης
    return os.path.join('private_uploads', 'leave_requests', str(instance.leave_request.id), filename)


class SecureFile(models.Model):
    """Κρυπτογραφημένο αρχείο"""
    
    ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png']
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB per workflow.txt
    
    leave_request = models.ForeignKey('LeaveRequest', on_delete=models.CASCADE, related_name='attachments')
    original_filename = models.CharField('Αρχικό Όνομα Αρχείου', max_length=255)
    file_path = models.CharField('Διαδρομή Αρχείου', max_length=500)
    file_size = models.PositiveIntegerField('Μέγεθος Αρχείου (bytes)')
    content_type = models.CharField('Τύπος Περιεχομένου', max_length=100)
    encryption_key = models.CharField('Κλειδί Κρυπτογράφησης', max_length=64)  # AES-256 key in hex
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_files')
    uploaded_at = models.DateTimeField('Ημερομηνία Αποστολής', auto_now_add=True)
    description = models.TextField('Περιγραφή Αρχείου', blank=True)
    
    class Meta:
        verbose_name = 'Ασφαλές Αρχείο'
        verbose_name_plural = 'Ασφαλή Αρχεία'
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.original_filename} - {self.leave_request}"
    
    @property
    def file_extension(self):
        """Επιστρέφει την επέκταση του αρχείου"""
        return self.original_filename.split('.')[-1].lower()
    
    def get_absolute_url(self):
        """URL για το secure download του αρχείου"""
        from django.urls import reverse
        return reverse('leaves:serve_secure_file', kwargs={'file_id': self.pk})


class LeaveRequest(models.Model):
    """Αίτηση άδειας"""
    
    STATUS_CHOICES = [
        ('DRAFT', 'Πρόχειρη αίτηση'),
        ('SUBMITTED', 'Υποβληθείσα αίτηση'),
        ('PENDING_KEDASY_PROTOCOL', 'Εκκρεμεί Πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ'),
        ('PENDING_PROTOCOL', 'Για πρωτόκολλο ΠΔΕΔΕ'),
        ('IN_REVIEW', 'Σε επεξεργασία από τμήμα αδειών'),
        ('WAITING_FOR_DOCUMENTS', 'Σε αναμονή δικαιολογητικών'),
        ('DECISION_PREPARATION', 'Ετοιμασία απόφασης'),
        ('PENDING_YC_COMMITTEE', 'Αναμονή απόφασης Υγειονομικής Επιτροπής'),
        ('PENDING_SIGNATURES', 'ΣΗΔΕ - προς υπογραφές'),
        ('COMPLETED', 'Ολοκληρώθηκε'),
        ('SUPERVISOR_REJECTED', 'Αρνητική έγκριση προϊσταμένου'),
        ('REJECTED_BY_LEAVES_DEPT', 'Απόρριψη από τμήμα αδειών'),
        ('CANCELLED_BY_APPLICANT', 'Ανάκληση από αιτούντα'),
    ]
    
    # Βασικά πεδία
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests', verbose_name='Χρήστης')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, verbose_name='Τύπος Άδειας')
    description = models.TextField('Περιγραφή/Αιτιολογία', blank=True)
    requested_days = models.PositiveIntegerField('Αιτούμενες Ημέρες Άδειας', default=1,
        help_text='Συνολικός αριθμός ημερών άδειας που αιτείται ο χρήστης')
    days = models.PositiveIntegerField('Ημέρες Άδειας', default=1,
        help_text='Συνολικός αριθμός ημερών άδειας')

    # Στάτους και ημερομηνίες
    status = models.CharField('Κατάσταση', max_length=40, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    updated_at = models.DateTimeField('Ημερομηνία Ενημέρωσης', auto_now=True)
    submitted_at = models.DateTimeField('Ημερομηνία Υποβολής', null=True, blank=True)
    
    # Έγκριση από προϊστάμενο
    manager_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                          related_name='approved_leaves', verbose_name='Εγκρίθηκε από Προϊστάμενο')
    manager_approved_at = models.DateTimeField('Ημερομηνία Έγκρισης Προϊσταμένου', null=True, blank=True)
    manager_comments = models.TextField('Σχόλια Προϊσταμένου', blank=True)
    
    # Πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ (για τμήματα ΚΕΔΑΣΥ και ΚΕΠΕΑ)
    kedasy_kepea_protocol_number = models.CharField('Αριθμός Πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ', max_length=100, blank=True)
    kedasy_kepea_protocol_date = models.DateTimeField('Ημερομηνία Πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ', null=True, blank=True)
    kedasy_kepea_protocol_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                               related_name='kedasy_kepea_protocols', verbose_name='Πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ από')

    # Πρωτόκολλο ΠΔΕΔΕ/ΣΗΔΕ (για τον χειριστή αδειών)
    pdede_protocol_number = models.CharField('Αριθμός Πρωτοκόλλου ΠΔΕΔΕ', max_length=100, blank=True)
    pdede_protocol_date = models.DateTimeField('Ημερομηνία Πρωτοκόλλου ΠΔΕΔΕ', null=True, blank=True)
    pdede_protocol_details = models.TextField('Στοιχεία Πρωτοκόλλου ΠΔΕΔΕ', blank=True)
    pdede_protocol_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='pdede_protocols', verbose_name='Πρωτοκολλήθηκε από (ΠΔΕΔΕ)')

    # Επεξεργασία από χειριστή
    protocol_number = models.CharField('Αριθμός Πρωτοκόλλου', max_length=100, blank=True)
    protocol_pdf_path = models.CharField('Διαδρομή Πρωτοκολλημένου PDF', max_length=500, blank=True)
    protocol_pdf_encryption_key = models.CharField('Κλειδί Κρυπτογράφησης Πρωτοκόλλου', max_length=64, blank=True)
    protocol_pdf_size = models.PositiveIntegerField('Μέγεθος Πρωτοκολλημένου PDF', null=True, blank=True)
    protocol_created_at = models.DateTimeField('Ημερομηνία Πρωτοκόλλησης', null=True, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='processed_leaves', verbose_name='Επεξεργάστηκε από')
    processed_at = models.DateTimeField('Ημερομηνία Επεξεργασίας', null=True, blank=True)
    processing_comments = models.TextField('Σχόλια Επεξεργασίας', blank=True)
    
    # Ολοκλήρωση
    completed_at = models.DateTimeField('Ημερομηνία Ολοκλήρωσης', null=True, blank=True)
    
    # Απόρριψη
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='rejected_leaves', verbose_name='Απορρίφθηκε από')
    rejected_at = models.DateTimeField('Ημερομηνία Απόρριψης', null=True, blank=True)
    rejection_reason = models.TextField('Λόγος Απόρριψης', blank=True)
    
    # Επιστροφή στον αιτούντα
    return_notes = models.TextField('Σημειώσεις Επιστροφής', blank=True)
    returned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='returned_leaves', verbose_name='Επιστράφηκε από')
    returned_at = models.DateTimeField('Ημερομηνία Επιστροφής', null=True, blank=True)
    
    # Notifications
    notifications = GenericRelation(Notification)
    
    # Πεδία για απόφαση PDF
    decision_logo = models.ForeignKey('Logo', on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name='Λογότυπο Απόφασης')
    decision_info = models.ForeignKey('Info', on_delete=models.SET_NULL, null=True, blank=True,
                                    verbose_name='Πληροφορίες Απόφασης')
    decision_ypopsin = models.ForeignKey('Ypopsin', on_delete=models.SET_NULL, null=True, blank=True,
                                       verbose_name='Έχοντας Υπόψη Απόφασης')
    decision_signee = models.ForeignKey('Signee', on_delete=models.SET_NULL, null=True, blank=True,
                                      verbose_name='Υπογράφων Απόφασης')
    final_decision_text = models.TextField('Τελικό Κείμενο Απόφασης', blank=True)
    decision_pdf_path = models.CharField('Διαδρομή PDF Απόφασης', max_length=500, blank=True)
    decision_pdf_encryption_key = models.CharField('Κλειδί Κρυπτογράφησης Απόφασης', max_length=64, blank=True)
    decision_pdf_size = models.PositiveIntegerField('Μέγεθος PDF Απόφασης', null=True, blank=True)
    decision_created_at = models.DateTimeField('Ημερομηνία Δημιουργίας Απόφασης', null=True, blank=True)
    
    # Πεδία για το Ακριβές αντίγραφο από ΣΗΔΕ
    exact_copy_pdf_path = models.CharField('Διαδρομή Ακριβούς Αντιγράφου', max_length=500, blank=True)
    exact_copy_pdf_encryption_key = models.CharField('Κλειδί Κρυπτογράφησης Ακριβούς Αντιγράφου', max_length=64, blank=True)
    exact_copy_pdf_size = models.PositiveIntegerField('Μέγεθος Ακριβούς Αντιγράφου', null=True, blank=True)
    exact_copy_uploaded_at = models.DateTimeField('Ημερομηνία Αποστολής Ακριβούς Αντιγράφου', null=True, blank=True)
    exact_copy_uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                             related_name='uploaded_exact_copies', verbose_name='Ανέβασε το Ακριβές Αντίγραφο')
    
    # Πεδία για το Ενοποιημένο PDF (αίτηση + συνημμένα)
    merged_pdf_path = models.CharField('Διαδρομή Ενοποιημένου PDF', max_length=500, blank=True)
    merged_pdf_encryption_key = models.CharField('Κλειδί Κρυπτογράφησης Ενοποιημένου PDF', max_length=64, blank=True)
    merged_pdf_size = models.PositiveIntegerField('Μέγεθος Ενοποιημένου PDF', null=True, blank=True)
    merged_pdf_created_at = models.DateTimeField('Ημερομηνία Δημιουργίας Ενοποιημένου PDF', null=True, blank=True)
    merged_pdf_sent_at = models.DateTimeField('Ημερομηνία Αποστολής Email', null=True, blank=True)
    
    # Πεδία για διαχείριση δικαιολογητικών
    required_documents = models.TextField('Απαιτούμενα Δικαιολογητικά', blank=True,
                                        help_text='Περιγραφή των δικαιολογητικών που χρειάζονται')
    documents_deadline = models.DateTimeField('Προθεσμία Κατάθεσης Δικαιολογητικών', null=True, blank=True)
    documents_requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                             related_name='requested_documents', verbose_name='Ζήτησε Δικαιολογητικά')
    documents_requested_at = models.DateTimeField('Ημερομηνία Αιτήματος Δικαιολογητικών', null=True, blank=True)
    documents_provided_at = models.DateTimeField('Ημερομηνία Παροχής Δικαιολογητικών', null=True, blank=True)
    documents_provided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                            related_name='provided_documents', verbose_name='Παρείχε Δικαιολογητικά')
    documents_notes = models.TextField('Σημειώσεις Δικαιολογητικών', blank=True)
    
    # Ανάκληση και κλείδωμα
    parent_leave = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='child_requests', verbose_name='Γονική Αίτηση',
                                     help_text='Για ανάκληση/μερική ανάκληση - συνδέει με την αρχική αίτηση')
    revoked_days = models.IntegerField('Ανακληθείσες Ημέρες', default=0,
                                       help_text='Ημέρες που ανακλήθηκαν από την αρχική αίτηση')
    locking_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='locked_leaves', verbose_name='Κλειδωμένο από Χειριστή')
    locked_at = models.DateTimeField('Ώρα Κλειδώματος', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Αίτηση Άδειας'
        verbose_name_plural = 'Αιτήσεις Αδειών'
        ordering = ['-created_at']
        permissions = [
            ('can_approve_leave', 'Μπορεί να εγκρίνει άδειες'),
            ('can_process_leave', 'Μπορεί να επεξεργαστεί άδειες'),
        ]
    
    def __str__(self):
        if self.start_date and self.end_date:
            return f"{self.user.full_name} - {self.leave_type.name} ({self.start_date} - {self.end_date})"
        return f"{self.user.full_name} - {self.leave_type.name} ({self.total_days} ημέρες)"
    
    @property
    def total_days(self):
        """Υπολογισμός συνολικών ημερών άδειας από όλα τα διαστήματα"""
        return sum(period.days for period in self.periods.all())

    @property
    def start_date(self):
        """Πρώτη ημερομηνία έναρξης από όλα τα διαστήματα"""
        periods = self.periods.all().order_by('start_date')
        if periods:
            return periods.first().start_date
        return None

    @property
    def end_date(self):
        """Τελευταία ημερομηνία λήξης από όλα τα διαστήματα"""
        periods = self.periods.all().order_by('-end_date')
        if periods:
            return periods.first().end_date
        return None

    @property
    def submission_datetime(self):
        """Ημερομηνία/ώρα υποβολής (με fallback σε created_at για παλιές εγγραφές)."""
        if self.submitted_at:
            return self.submitted_at
        if self.status != 'DRAFT':
            return self.created_at
        return None
    
    @property
    def can_be_edited(self):
        """Ελέγχει αν η αίτηση μπορεί να επεξεργαστεί"""
        return self.status == 'DRAFT'
    
    @property
    def can_be_approved_by_manager(self):
        """Ελέγχει αν η αίτηση μπορεί να εγκριθεί από προϊστάμενο"""
        return self.status == 'SUBMITTED'

    def can_be_approved_by(self, manager):
        """Ελέγχει αν ο συγκεκριμένος προϊστάμενος μπορεί να εγκρίνει/απορρίψει την αίτηση"""
        if not self.can_be_approved_by_manager or not manager:
            return False
        if not manager.is_department_manager or self.user == manager:
            return False

        approving_manager = self.user.get_approving_manager()
        if approving_manager and approving_manager.id == manager.id:
            return True

        if (manager.department and manager.department.department_type and
                manager.department.department_type.code == 'KEDASY' and
                is_sdey_department(self.user.department) and
                self.user.department.parent_department == manager.department):
            return True

        return False
    
    @property
    def can_be_processed(self):
        """Ελέγχει αν η αίτηση μπορεί να επεξεργαστεί από χειριστή"""
        return self.status in ['PENDING_PROTOCOL', 'WAITING_FOR_DOCUMENTS', 'IN_REVIEW', 'DECISION_PREPARATION', 'PENDING_YC_COMMITTEE']
    
    @property
    def is_pending(self):
        """Ελέγχει αν η αίτηση είναι εκκρεμής"""
        return self.status in ['SUBMITTED', 'PENDING_PROTOCOL', 'WAITING_FOR_DOCUMENTS', 'IN_REVIEW']
    
    @property
    def is_completed(self):
        """Ελέγχει αν η αίτηση έχει ολοκληρωθεί"""
        return self.status == 'COMPLETED'

    @property
    def is_approved(self):
        """Ελέγχει αν η αίτηση έχει ολοκληρωθεί επιτυχώς"""
        return self.status == 'COMPLETED'
    
    @property
    def is_rejected(self):
        """Ελέγχει αν η αίτηση έχει απορριφθεί"""
        return self.status in ['SUPERVISOR_REJECTED', 'REJECTED_BY_LEAVES_DEPT']
    
    @property
    def is_withdrawn(self):
        """Ελέγχει αν η αίτηση έχει ανακληθεί"""
        return self.status == 'CANCELLED_BY_APPLICANT'
    
    @property
    def can_be_withdrawn(self):
        """Ελέγχει αν η αίτηση μπορεί να ανακληθεί από τον αιτούντα"""
        return self.status in ['SUBMITTED', 'PENDING_KEDASY_PROTOCOL']
    
    def get_approving_manager(self):
        """Επιστρέφει τον προϊστάμενο που πρέπει να εγκρίνει την αίτηση"""
        return self.user.get_approving_manager()
    
    def submit(self):
        """Υποβολή αίτησης"""
        if self.status == 'DRAFT':
            if self.leave_type.is_sick_leave_yd:
                used = LeaveRequest.objects.filter(
                    user=self.user,
                    leave_type__is_sick_leave_yd=True,
                    status='COMPLETED',
                    submitted_at__year=timezone.now().year
                ).count()
                if used >= self.user.sick_leave_with_declaration:
                    raise ValueError(
                        f"Εξαντλήσατε το ετήσιο όριο αναρρωτικών αδειών με ΥΔ "
                        f"({self.user.sick_leave_with_declaration}/έτος)."
                    )

            if self.leave_type.affects_regular_leave_balance:
                if not self.user.can_request_leave_days(self.total_days):
                    raise ValueError(
                        f"Ανεπαρκές υπόλοιπο αδειών. "
                        f"Διαθέσιμες: {self.user.leave_balance}, "
                        f"Αιτούμενες: {self.total_days}"
                    )

            if self.requires_kedasy_kepea_protocol():
                self.status = 'PENDING_KEDASY_PROTOCOL'
            elif self.leave_type.requires_approval:
                self.status = 'SUBMITTED'
            else:
                self.status = 'PENDING_PROTOCOL'
            self.submitted_at = timezone.now()
            self.save()
            from leaves.utils.sick_leave_alerts import handle_sick_threshold_on_submit
            handle_sick_threshold_on_submit(self)
            return True
        return False
    
    def approve_by_manager(self, manager, comments=''):
        """Έγκριση από προϊστάμενο"""
        if not self.can_be_approved_by(manager):
            return False

        if self.leave_type.is_simple:
            self.status = 'COMPLETED'
            self.manager_approved_by = manager
            self.manager_approved_at = timezone.now()
            self.manager_comments = comments
            self.completed_at = timezone.now()
            self.processed_by = manager
            self.processed_at = timezone.now()
            self.save()
            self._update_leave_balance_on_completion(created_by=manager)
            return True

        self.status = 'PENDING_PROTOCOL'
        self.manager_approved_by = manager
        self.manager_approved_at = timezone.now()
        self.manager_comments = comments
        self.save()
        return True
    
    def reject_by_manager(self, manager, reason):
        """Απόρριψη από προϊστάμενο"""
        if not self.can_be_approved_by(manager):
            return False
        if not reason or not str(reason).strip():
            return False

        self.status = 'SUPERVISOR_REJECTED'
        self.rejected_by = manager
        self.rejected_at = timezone.now()
        self.rejection_reason = reason.strip()
        self.save()
        return True
    
    def start_processing(self, handler, protocol_number='', comments=''):
        """Έναρξη επεξεργασίας από χειριστή"""
        if self.can_be_processed:
            self.status = 'IN_REVIEW'
            if protocol_number:
                self.protocol_number = protocol_number
            self.processing_comments = comments
            self.processed_by = handler
            self.processed_at = timezone.now()
            self.save()
            return True
        return False
    
    def complete(self):
        """Ολοκλήρωση αίτησης"""
        if self.status == 'IN_REVIEW':
            self.status = 'COMPLETED'
            self.completed_at = timezone.now()
            self.save()
            # Ενημέρωση leave balance
            self._update_leave_balance_on_completion()
            return True
        return False
    
    def complete_by_handler(self, handler, comments='', balance_after=None):
        """Ολοκλήρωση αίτησης από χειριστή"""
        if not handler.is_leave_handler:
            return False
        if self.status != 'IN_REVIEW':
            return False
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        # Ενημερώνουμε τα πεδία επεξεργασίας μόνο κατά την τελική ολοκλήρωση
        if not self.processed_by:
            self.processed_by = handler
        if not self.processed_at:
            self.processed_at = timezone.now()
        if comments:
            self.processing_comments = comments
        self.save()
        self._update_leave_balance_on_completion(
            created_by=handler,
            balance_after=balance_after,
        )
        return True
    
    def _update_leave_balance_on_completion(self, created_by=None, balance_after=None):
        """Ενημερώνει το leave balance όταν η αίτηση ολοκληρώνεται"""
        import logging
        logger = logging.getLogger(__name__)

        if self.status == 'COMPLETED':
            if self.leave_type.affects_regular_leave_balance:
                days_used = self.total_days
                if days_used > 0:
                    from leaves.utils.balance_ledger import create_balance_entry, get_last_balance

                    last_balance = get_last_balance(self.user)
                    if last_balance is None:
                        last_balance = self.user.current_regular_leave_balance

                    if balance_after is None:
                        balance_after = max(0, last_balance - days_used)

                    days_delta = balance_after - last_balance if last_balance is not None else -days_used
                    create_balance_entry(
                        employee=self.user,
                        entry_type='LEAVE_GRANTED',
                        description=(
                            f'Ολοκλήρωση άδειας #{self.id} — {self.leave_type.name}'
                        ),
                        balance_after=balance_after,
                        leave_request=self,
                        days_delta=days_delta,
                        notes=f'Ημερομηνίες: {self.start_date} - {self.end_date}',
                        created_by=created_by,
                    )
                    logger.info(
                        f"Deducted {days_used} leave days for user {self.user} "
                        f"on completion of request {self.id} (balance_after={balance_after})"
                    )

            if self.leave_type.is_sick_leave_total:
                current_year = timezone.now().year
                yearly_total, _ = YearlySickLeaveTotal.objects.get_or_create(
                    employee=self.user,
                    year=current_year,
                    defaults={'total_days': 0}
                )
                yearly_total.total_days += self.total_days
                yearly_total.save()
                self.user.sick_days_current_year = yearly_total.total_days
                self.user.save(update_fields=['sick_days_current_year'])
    
    def reject_by_operator(self, operator, reason):
        """Απόρριψη από χειριστή"""
        if self.status in ['PENDING_PROTOCOL', 'IN_REVIEW']:
            self.status = 'REJECTED_BY_LEAVES_DEPT'
            self.rejected_by = operator
            self.rejected_at = timezone.now()
            self.rejection_reason = reason
            self.save()
            return True
        return False
    
    def reject_by_handler(self, handler, reason):
        """Απόρριψη από χειριστή"""
        if self.status in [
            'PENDING_PROTOCOL', 'IN_REVIEW', 'WAITING_FOR_DOCUMENTS',
            'DECISION_PREPARATION', 'PENDING_SIGNATURES',
        ]:
            self.status = 'REJECTED_BY_LEAVES_DEPT'
            self.rejected_by = handler
            self.rejected_at = timezone.now()
            self.rejection_reason = reason
            self.save()
            return True
        return False
    
    def withdraw_by_requester(self, user):
        """Ανάκληση αίτησης από τον αιτούντα"""
        if self.user != user:
            raise ValueError("Μόνο ο αιτούντας μπορεί να ανακαλέσει την αίτηση")
        
        if not self.can_be_withdrawn:
            raise ValueError("Η αίτηση δεν μπορεί να ανακληθεί σε αυτή τη φάση")
        
        self.status = 'CANCELLED_BY_APPLICANT'
        self.rejected_by = user
        self.rejected_at = timezone.now()
        self.rejection_reason = 'Ανάκληση αίτησης από τον αιτούντα'
        self.save()
        return True
    
    def request_documents(self, handler, required_documents, deadline=None):
        """Αίτημα για δικαιολογητικά από χειριστή"""
        if not self.status in ['IN_REVIEW']:
            raise ValueError("Δεν μπορεί να ζητηθούν δικαιολογητικά σε αυτή τη φάση")
        
        self.status = 'WAITING_FOR_DOCUMENTS'
        self.required_documents = required_documents
        self.documents_deadline = deadline
        self.documents_requested_by = handler
        self.documents_requested_at = timezone.now()
        self.save()
        return True
    
    def provide_documents(self, handler, notes=''):
        """Παροχή δικαιολογητικών (από χειριστή)"""
        if self.status != 'WAITING_FOR_DOCUMENTS':
            raise ValueError("Δεν είναι σε αναμονή δικαιολογητικών")
        
        self.status = 'IN_REVIEW'
        self.documents_provided_by = handler
        self.documents_provided_at = timezone.now()
        self.documents_notes = notes
        self.save()
        return True
    
    @property
    def is_pending_documents(self):
        """Ελέγχει αν η αίτηση είναι σε αναμονή δικαιολογητικών"""
        return self.status == 'WAITING_FOR_DOCUMENTS'
    
    @property
    def is_documents_overdue(self):
        """Ελέγχει αν η προθεσμία δικαιολογητικών έχει λήξει"""
        if self.status == 'WAITING_FOR_DOCUMENTS' and self.documents_deadline:
            return timezone.now() > self.documents_deadline
        return False
    
    @property
    def can_provide_documents(self):
        """Ελέγχει αν ο χρήστης μπορεί να παρέχει δικαιολογητικά"""
        return self.status == "WAITING_FOR_DOCUMENTS"

    @property
    def can_request_documents(self):
        """Ελέγχει αν ο χειριστής μπορεί να ζητήσει δικαιολογητικά"""
        return self.status == "IN_REVIEW"

    @property
    def can_send_to_yc(self):
        """Ελέγχει αν μπορεί να σταλεί σε Υγειονομική Επιτροπή"""
        if self.status != 'IN_REVIEW':
            return False
        from leaves.utils.sick_leave_alerts import user_exceeds_sick_threshold
        return user_exceeds_sick_threshold(self.user)

    def send_to_yc_committee(self, handler, notes=''):
        """Αποστολή σε Υγειονομική Επιτροπή"""
        if not self.can_send_to_yc:
            raise ValueError("Η αίτηση δεν μπορεί να σταλεί σε Υγειονομική Επιτροπή")
        self.status = 'PENDING_YC_COMMITTEE'
        self.processing_comments = notes
        self.save()
        return True

    def receive_from_yc_committee(self, handler, notes=''):
        """Επιστροφή από Υγειονομική Επιτροπή (συνέχεια κανονικής ροής)"""
        if self.status != 'PENDING_YC_COMMITTEE':
            raise ValueError("Η αίτηση δεν είναι σε αναμονή απόφασης Υγειονομικής Επιτροπής")
        self.status = 'IN_REVIEW'
        if notes:
            self.processing_comments = notes
        self.save()
        return True
    
    def has_protocol_pdf(self):
        """Επιστρέφει True αν υπάρχει πρωτοκολλημένο PDF"""
        return bool(self.protocol_pdf_path and self.protocol_pdf_encryption_key)
    
    def get_protocol_pdf_url(self):
        """URL για το πρωτοκολλημένο PDF"""
        if self.has_protocol_pdf():
            from django.urls import reverse
            return reverse('leaves:serve_protocol_pdf', kwargs={'pk': self.pk})
        return None
    
    def has_decision_pdf(self):
        """Επιστρέφει True αν υπάρχει PDF απόφασης"""
        return bool(self.decision_pdf_path and self.decision_pdf_encryption_key)
    
    def get_decision_pdf_url(self):
        """URL για το PDF απόφασης"""
        if self.has_decision_pdf():
            from django.urls import reverse
            return reverse('leaves:serve_decision_pdf', kwargs={'pk': self.pk})
        return None
    
    def has_exact_copy_pdf(self):
        """Επιστρέφει True αν υπάρχει ακριβές αντίγραφο PDF"""
        return bool(self.exact_copy_pdf_path and self.exact_copy_pdf_encryption_key)
    
    def has_merged_pdf(self):
        """Επιστρέφει True αν υπάρχει ενοποιημένο PDF"""
        return bool(self.merged_pdf_path and self.merged_pdf_encryption_key)
    
    def get_exact_copy_pdf_url(self):
        """URL για το ακριβές αντίγραφο PDF"""
        if self.has_exact_copy_pdf():
            from django.urls import reverse
            return reverse('leaves:serve_exact_copy_pdf', kwargs={'pk': self.pk})
        return None
    
    def can_upload_exact_copy(self):
        """Ελέγχει αν μπορεί να ανέβει ακριβές αντίγραφο"""
        return self.has_decision_pdf() and self.status in ['IN_REVIEW', 'PENDING_SIGNATURES']

    def can_complete_request(self):
        """Ελέγχει αν μπορεί να ολοκληρωθεί η αίτηση"""
        return self.has_exact_copy_pdf() and self.status in ['IN_REVIEW', 'PENDING_SIGNATURES']
    
    def can_create_decision(self):
        """Ελέγχει αν μπορεί να δημιουργηθεί απόφαση"""
        return self.status in ['IN_REVIEW', 'DECISION_PREPARATION', 'PENDING_SIGNATURES']

    def notify_sick_leave_threshold_exceeded(self):
        """
        Ειδοποιήσεις όταν το σύνολο αναρρωτικών (ενεργές + ολοκληρωμένες αιτήσεις)
        ξεπερνά τις 8 ημέρες — σε χειριστές, προϊστάμενο και υπάλληλο.
        """
        if not self.leave_type.is_sick_leave_total:
            return

        from notifications.utils import create_notification as _create_notification
        from leaves.utils.sick_leave_alerts import calculate_yearly_sick_total

        current_year = timezone.now().year
        sick_total = calculate_yearly_sick_total(self.user, year=current_year)

        if sick_total <= 8:
            return

        from accounts.models import User
        message_base = (
            f"Ο/Η {self.user.full_name} έχει συνολικά {sick_total} αναρρωτικές ημέρες "
            f"στο τρέχον έτος (όριο: 8). Απαιτείται παραπομπή στην Υγειονομική Επιτροπή."
        )

        handlers = User.objects.filter(roles__code='LEAVE_HANDLER', is_active=True)
        for handler in handlers:
            _create_notification(
                user=handler,
                title="Υπέρβαση Αναρρωτικών — Απαιτείται Υγειονομική Επιτροπή",
                message=message_base,
                related_object=self,
            )

        manager = self.user.get_approving_manager()
        if manager:
            _create_notification(
                user=manager,
                title="Υπέρβαση Αναρρωτικών — Απαιτείται Υγειονομική Επιτροπή",
                message=message_base,
                related_object=self,
            )

        _create_notification(
            user=self.user,
            title="Υπέρβαση Αναρρωτικών — Απαιτείται Υγειονομική Επιτροπή",
            message=(
                f"Το σύνολο των αναρρωτικών σας αδειών ανέρχεται σε {sick_total} ημέρες "
                f"(όριο: 8). Θα παραπεμφθείτε στην Υγειονομική Επιτροπή."
            ),
            related_object=self,
        )

    def _notify_sick_leave_threshold_exceeded(self):
        """Backward-compatible alias."""
        self.notify_sick_leave_threshold_exceeded()

    def start_decision_preparation(self, user):
        """Μεταφορά σε κατάσταση ετοιμασίας απόφασης"""
        if self.status == 'IN_REVIEW':
            self.status = 'DECISION_PREPARATION'
            self.save()
            return True
        return False

    def send_to_signatures(self, user):
        """Προώθηση προς υπογραφές ΣΗΔΕ"""
        if self.status == 'DECISION_PREPARATION':
            self.status = 'PENDING_SIGNATURES'
            self.save()
            return True
        return False

    def finalize_with_exact_copy(self, user):
        """Ολοκλήρωση αίτησης μετά το ανέβασμα ακριβούς αντιγράφου ΣΗΔΕ"""
        if self.has_exact_copy_pdf() and self.status in ['IN_REVIEW', 'PENDING_SIGNATURES']:
            self.status = 'COMPLETED'
            self.completed_at = timezone.now()
            if not self.processed_by:
                self.processed_by = user
            if not self.processed_at:
                self.processed_at = timezone.now()
            self.save()
            self._update_leave_balance_on_completion()
            return True
        return False
    
    def get_end_date(self):
        """Υπολογίζει την ημερομηνία λήξης της άδειας"""
        if self.start_date and self.total_days:
            from datetime import timedelta
            return self.start_date + timedelta(days=self.total_days - 1)
        return None
    
    @property
    def days_requested(self):
        """Alias για total_days για compatibility"""
        return self.total_days
    
    def get_status_display_class(self):
        """CSS κλάση για το status badge"""
        status_classes = {
            'DRAFT': 'secondary',
            'SUBMITTED': 'warning',
            'PENDING_PROTOCOL': 'info',
            'IN_REVIEW': 'primary',
            'WAITING_FOR_DOCUMENTS': 'warning',
            'DECISION_PREPARATION': 'info',
            'PENDING_YC_COMMITTEE': 'danger',
            'PENDING_SIGNATURES': 'warning',
            'COMPLETED': 'success',
            'SUPERVISOR_REJECTED': 'danger',
            'REJECTED_BY_LEAVES_DEPT': 'danger',
            'CANCELLED_BY_APPLICANT': 'warning',
        }
        return status_classes.get(self.status, 'secondary')
    
    def can_user_view(self, user):
        """Ελέγχει αν ο χρήστης μπορεί να δει την αίτηση"""
        # Ο ιδιοκτήτης μπορεί πάντα να δει
        if self.user == user:
            return True
        
        # Οι προϊστάμενοι μπορούν να δουν αιτήσεις του τμήματός τους
        if user.is_department_manager and self.user.department == user.department:
            return True

        # Προϊστάμενος PDEDE — πρόσβαση σε όλες τις αιτήσεις
        if (user.is_department_manager and user.department and
                user.department.department_type and
                user.department.department_type.code == 'PDEDE_MAIN'):
            return True
        
        # Οι προϊστάμενοι ΚΕΔΑΣΥ μπορούν να δουν και αιτήσεις από ΣΔΕΥ
        if (user.is_department_manager and
            user.department and user.department.department_type and
            user.department.department_type.code == 'KEDASY' and
            is_sdey_department(self.user.department) and
            self.user.department.parent_department == user.department):
            return True
        
        # Οι χειριστές μπορούν να δουν όλες τις αιτήσεις
        if user.is_leave_handler:
            return True
        
        # Οι γραμματείς μπορούν να δουν αιτήσεις του τμήματός τους
        if user.is_secretary:
            if self.user.department == user.department:
                return True
            if (user.department and user.department.department_type and
                user.department.department_type.code == 'KEDASY' and
                is_sdey_department(self.user.department) and
                self.user.department.parent_department == user.department):
                return True
        
        return False
    
    def get_next_actions(self, user):
        """Επιστρέφει τις επόμενες δυνατές ενέργειες για τον χρήστη"""
        actions = []
        
        if self.user == user and self.can_be_edited:
            actions.append('edit')
        
        # Ο αιτούντας μπορεί να ανακαλέσει την αίτηση
        if self.user == user and self.can_be_withdrawn:
            actions.append('withdraw')
        
        # Προϊστάμενοι μπορούν να εγκρίνουν αιτήσεις που τους αναφέρονται
        if self.can_be_approved_by(user):
            actions.extend(['approve', 'reject'])
        
        if user.is_leave_handler and self.can_be_processed:
            if self.status == 'PENDING_PROTOCOL':
                actions.extend(['reject', 'request_documents'])
        
        if user.is_leave_handler and self.status == 'IN_REVIEW':
            actions.extend(['complete', 'reject', 'return'])
        
        if user.is_leave_handler and self.status == 'WAITING_FOR_DOCUMENTS':
            actions.extend(['upload_docs', 'return', 'reject'])
        
        if user.is_leave_handler and self.status in ['DECISION_PREPARATION', 'PENDING_SIGNATURES']:
            actions.append('reject')

        return actions
    
    def requires_kedasy_kepea_protocol(self):
        """Αν η αίτηση ακολουθεί ροή πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ (variant + τμήμα)."""
        from leaves.workflow_routing import leave_request_requires_kedasy_protocol
        return leave_request_requires_kedasy_protocol(self)

    def is_kedasy_kepea_department(self):
        """Έλεγχος αν το τμήμα είναι ΚΕΔΑΣΥ, ΚΕΠΕΑ ή ΣΔΕΥ (μόνο department)."""
        try:
            department = self.user.department
            if department and department.department_type:
                # Άμεσα τμήματα ΚΕΔΑΣΥ/ΚΕΠΕΑ
                if department.department_type.code in ['KEDASY', 'KEPEA']:
                    return True
                # ΣΔΕΥ που ανήκουν σε ΚΕΔΑΣΥ (SDEY ή legacy SDEI)
                elif is_sdey_under_kedasy(department):
                    return True
        except AttributeError:
            pass
        return False
    
    def can_add_kedasy_kepea_protocol(self, user):
        """Έλεγχος αν ο χρήστης μπορεί να προσθέσει πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ"""
        if not user.is_authenticated:
            return False
        
        # Έλεγχος αν είναι τμήμα ΚΕΔΑΣΥ/ΚΕΠΕΑ/ΣΔΕΥ
        if not self.requires_kedasy_kepea_protocol():
            return False
        
        # Έλεγχος αν το status είναι PENDING_KEDASY_PROTOCOL
        if self.status != 'PENDING_KEDASY_PROTOCOL':
            return False
        
        # Έλεγχος αν ο χρήστης έχει ρόλο Secretary ή Manager
        try:
            department = self.user.department
            if department and user.department:
                user_has_permission = user.roles.filter(code__in=['SECRETARY', 'MANAGER']).exists()
                if not user_has_permission:
                    return False
                
                # Για ΚΕΔΑΣΥ/ΚΕΠΕΑ: Ίδιο τμήμα
                if department.department_type.code in ['KEDASY', 'KEPEA']:
                    return user.department == department
                
                # Για ΣΔΕΥ: Ο χρήστης πρέπει να είναι Manager/Secretary του γονικού ΚΕΔΑΣΥ
                elif is_sdey_under_kedasy(department):
                    return user.department == department.parent_department
                
        except AttributeError:
            pass
        
        return False
    
    def save_pdede_protocol_details(self, protocol_number, protocol_date, protocol_details='', user=None):
        """Αποθήκευση στοιχείων ΠΔΕΔΕ/ΣΗΔΕ πρωτοκόλλου"""
        self.pdede_protocol_number = protocol_number
        self.pdede_protocol_date = protocol_date
        self.pdede_protocol_details = protocol_details
        if user:
            self.pdede_protocol_by = user
        self.save()
        return True

    def add_kedasy_kepea_protocol(self, protocol_number, protocol_date, user):
        """Προσθήκη πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ"""
        if not self.can_add_kedasy_kepea_protocol(user):
            raise ValueError("Δεν έχετε δικαίωμα να προσθέσετε πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ")
        
        self.kedasy_kepea_protocol_number = protocol_number
        self.kedasy_kepea_protocol_date = protocol_date
        self.kedasy_kepea_protocol_by = user
        
        # Αν δεν απαιτεί έγκριση, πάει κατευθείαν PENDING_PROTOCOL
        if not self.leave_type.requires_approval:
            self.status = 'PENDING_PROTOCOL'
            self.manager_approved_by = None
            self.manager_approved_at = None
            self.manager_comments = ""
        else:
            self.status = 'SUBMITTED'
            self.manager_approved_by = None
            self.manager_approved_at = None
            self.manager_comments = ""
        
        self.save()
        
        return True


class Logo(models.Model):
    """Λογότυπο της υπηρεσίας για τις αποφάσεις"""
    logo_short = models.CharField('Σύντομο Λογότυπο', max_length=100)
    logo = models.TextField('Πλήρες Λογότυπο')
    is_active = models.BooleanField('Ενεργό', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    updated_at = models.DateTimeField('Ημερομηνία Ενημέρωσης', auto_now=True)
    
    class Meta:
        verbose_name = 'Λογότυπο'
        verbose_name_plural = 'Λογότυπα'
        ordering = ['-is_active', '-created_at']
    
    def __str__(self):
        return self.logo_short
    
    @classmethod
    def get_active(cls):
        """Επιστρέφει το ενεργό λογότυπο"""
        return cls.objects.filter(is_active=True).first()


class Info(models.Model):
    """Πληροφορίες χειριστή αδειών για τις αποφάσεις"""
    info_short = models.CharField('Σύντομες Πληροφορίες', max_length=100)
    info = models.TextField('Πλήρεις Πληροφορίες')
    is_active = models.BooleanField('Ενεργό', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    updated_at = models.DateTimeField('Ημερομηνία Ενημέρωσης', auto_now=True)
    
    class Meta:
        verbose_name = 'Πληροφορίες'
        verbose_name_plural = 'Πληροφορίες'
        ordering = ['-is_active', '-created_at']
    
    def __str__(self):
        return self.info_short
    
    @classmethod
    def get_active(cls):
        """Επιστρέφει τις ενεργές πληροφορίες"""
        return cls.objects.filter(is_active=True).first()


class Ypopsin(models.Model):
    """Έχοντας υπόψη πληροφορίες για τις αποφάσεις"""
    ypopsin_short = models.CharField('Σύντομη Περιγραφή', max_length=200)
    ypopsin = models.TextField('Πλήρες Κείμενο Υπόψη')
    is_active = models.BooleanField('Ενεργό', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    updated_at = models.DateTimeField('Ημερομηνία Ενημέρωσης', auto_now=True)
    
    class Meta:
        verbose_name = 'Έχοντας Υπόψη'
        verbose_name_plural = 'Έχοντας Υπόψη'
        ordering = ['-is_active', '-created_at']
    
    def __str__(self):
        return self.ypopsin_short
    
    @classmethod
    def get_active(cls):
        """Επιστρέφει το ενεργό κείμενο υπόψη"""
        return cls.objects.filter(is_active=True).first()


class Signee(models.Model):
    """Στοιχεία υπογράφοντα των αποφάσεων"""
    signee_short = models.CharField('Σύντομη Περιγραφή', max_length=100)
    signee_name = models.CharField('Ονοματεπώνυμο', max_length=200)
    signee = models.TextField('Πλήρες Κείμενο Υπογραφής')
    is_active = models.BooleanField('Ενεργό', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    updated_at = models.DateTimeField('Ημερομηνία Ενημέρωσης', auto_now=True)
    
    class Meta:
        verbose_name = 'Υπογράφων'
        verbose_name_plural = 'Υπογράφοντες'
        ordering = ['-is_active', '-created_at']
    
    def __str__(self):
        return self.signee_name
    
    @classmethod
    def get_active(cls):
        """Επιστρέφει τον ενεργό υπογράφοντα"""
        return cls.objects.filter(is_active=True).first()


class PublicHoliday(models.Model):
    """Δημόσιες αργίες για υπολογισμό εργάσιμων ημερών"""
    name = models.CharField('Όνομα Αργίας', max_length=200)
    date = models.DateField('Ημερομηνία')
    is_movable = models.BooleanField('Κινητή Εορτή', default=False,
        help_text='True για κινητές εορτές (π.χ. Πάσχα), False για σταθερές')
    year = models.PositiveIntegerField('Έτος')
    is_active = models.BooleanField('Ενεργή', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='Δημιουργήθηκε από')

    class Meta:
        verbose_name = 'Δημόσια Αργία'
        verbose_name_plural = 'Δημόσιες Αργίες'
        ordering = ['date']
        unique_together = ['date', 'name']

    def __str__(self):
        return f"{self.name} - {self.date.strftime('%d/%m/%Y')}"


class LeaveActionLog(models.Model):
    """Audit trail για όλες τις αλλαγές κατάστασης αδειών"""
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE,
                                      related_name='action_logs', verbose_name='Αίτηση Άδειας')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                            related_name='leave_action_logs', verbose_name='Χρήστης')
    action = models.CharField('Ενέργεια', max_length=100)
    previous_status = models.CharField('Προηγούμενη Κατάσταση', max_length=50, blank=True)
    new_status = models.CharField('Νέα Κατάσταση', max_length=50, blank=True)
    timestamp = models.DateTimeField('Ημερομηνία/Ώρα', auto_now_add=True)
    notes = models.TextField('Σημειώσεις', blank=True)
    ip_address = models.GenericIPAddressField('IP Διεύθυνση', null=True, blank=True)

    class Meta:
        verbose_name = 'Log Ενέργειας Άδειας'
        verbose_name_plural = 'Logs Ενεργειών Αδειών'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} - {self.leave_request} ({self.timestamp.strftime('%d/%m/%Y %H:%M')})"


class LeaveAccessLog(models.Model):
    """GDPR compliance - tracking ποιος είδε/κατέβασε ποια αίτηση"""
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE,
                                      related_name='access_logs', verbose_name='Αίτηση Άδειας')
    accessed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='leave_access_logs', verbose_name='Πρόσβαση από')
    access_type = models.CharField('Τύπος Πρόσβασης', max_length=20,
                                   choices=[('VIEW', 'Προβολή'), ('DOWNLOAD', 'Λήψη')])
    timestamp = models.DateTimeField('Ημερομηνία/Ώρα', auto_now_add=True)
    ip_address = models.GenericIPAddressField('IP Διεύθυνση', null=True, blank=True)

    class Meta:
        verbose_name = 'Log Πρόσβασης Άδειας'
        verbose_name_plural = 'Logs Πρόσβασης Αδειών'
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.accessed_by} → {self.leave_request} ({self.access_type})"


class RegularLeaveBalanceEntry(models.Model):
    """
    Καρτέλα/Ιστορικό Υπολοίπου Κανονικών Αδειών
    Append-only ledger — κάθε εγγραφή είναι γεγονός που επηρεάζει ή επιβεβαιώνει το υπόλοιπο.
    """
    ENTRY_TYPES = [
        ('INITIAL_BALANCE', 'Αρχικό Υπόλοιπο'),
        ('LEAVE_GRANTED', 'Χορήγηση Κανονικής Άδειας'),
        ('LEAVE_REVOKED', 'Ανάκληση Άδειας'),
        ('MANUAL_ADJUSTMENT', 'Διοικητική Διόρθωση'),
        ('CARRYOVER_IMPORT', 'Μεταφορά Υπολοίπου'),
        ('PREVIOUS_YEAR_CORRECTION', 'Διόρθωση Προηγούμενου Έτους'),
        ('ADMIN_CORRECTION', 'Διόρθωση Χειριστή'),
    ]

    employee = models.ForeignKey(User, on_delete=models.CASCADE,
                                 related_name='regular_leave_balance_entries',
                                 verbose_name='Υπάλληλος')
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.SET_NULL,
                                      null=True, blank=True,
                                      related_name='balance_entries',
                                      verbose_name='Αίτηση Άδειας')
    entry_type = models.CharField('Τύπος Κίνησης', max_length=30, choices=ENTRY_TYPES)
    entry_date = models.DateField('Ημερομηνία Κίνησης')
    description = models.CharField('Περιγραφή', max_length=200)
    days_delta = models.IntegerField('Μεταβολή Ημερών', null=True, blank=True,
                                     help_text='Θετικό για επιστροφή, αρνητικό για αφαίρεση')
    balance_before = models.IntegerField('Υπόλοιπο Πριν', default=0,
                                         help_text='Υπόλοιπο πριν από την κίνηση')
    balance_after = models.IntegerField('Υπόλοιπο Μετά',
                                        help_text='Υπόλοιπο μετά την κίνηση (source of truth)')
    notes = models.TextField('Σημειώσεις', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_balance_entries',
                                   verbose_name='Δημιουργήθηκε από')
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    is_locked = models.BooleanField('Κλειδωμένο', default=True,
                                    help_text='Append-only — οι διορθώσεις είναι νέες εγγραφές')

    class Meta:
        verbose_name = 'Εγγραφή Υπολοίπου Κανονικών Αδειών'
        verbose_name_plural = 'Ιστορικό Υπολοίπου Κανονικών Αδειών'
        ordering = ['-entry_date', '-created_at']

    def __str__(self):
        return f"{self.employee} — {self.get_entry_type_display()} — {self.balance_after} ({self.entry_date.strftime('%d/%m/%Y')})"

    @property
    def delta_display(self):
        """Εμφάνιση μεταβολής με πρόσημο"""
        if self.days_delta is None:
            return '—'
        if self.days_delta > 0:
            return f'+{self.days_delta}'
        return str(self.days_delta)


class YearlySickLeaveTotal(models.Model):
    """Ετήσια καταγραφή συνόλου αναρρωτικών αδειών ανά υπάλληλο"""
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='yearly_sick_leave_totals',
                                  verbose_name='Υπάλληλος')
    year = models.PositiveIntegerField('Έτος')
    total_days = models.PositiveIntegerField('Σύνολο Ημερών', default=0)
    is_locked = models.BooleanField('Κλειδωμένο', default=False,
        help_text='Αν είναι ενεργό, η εγγραφή δεν μπορεί να τροποποιηθεί')
    notes = models.TextField('Σημειώσεις', blank=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)

    class Meta:
        verbose_name = 'Ετήσιο Σύνολο Αναρρωτικών'
        verbose_name_plural = 'Ετήσια Σύνολα Αναρρωτικών'
        unique_together = ['employee', 'year']
        ordering = ['-year', 'employee__last_name', 'employee__first_name']

    def __str__(self):
        return f"{self.employee} - {self.year}: {self.total_days} ημέρες"


class YCCommitteeAcknowledgment(models.Model):
    """Καταγραφή ότι ένας χειριστής έλαβε γνώση για την υπέρβαση αναρρωτικών ενός υπαλλήλου"""
    handler = models.ForeignKey(User, on_delete=models.CASCADE, related_name='yc_acknowledgments',
                                verbose_name='Χειριστής')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='yc_acknowledged_by',
                                 verbose_name='Υπάλληλος')
    acknowledged_at = models.DateTimeField('Ημερομηνία Γνώσης', auto_now_add=True)

    class Meta:
        verbose_name = 'Γνωμάτευση Υγειονομικής Επιτροπής'
        verbose_name_plural = 'Γνώσεις Υγειονομικής Επιτροπής'
        unique_together = ['handler', 'employee']
        ordering = ['-acknowledged_at']

    def __str__(self):
        return f"{self.handler} → {self.employee} ({self.acknowledged_at.strftime('%d/%m/%Y')})"
