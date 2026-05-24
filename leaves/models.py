import os
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation
from notifications.models import Notification

User = get_user_model()


class LeaveType(models.Model):
    """Τύπος άδειας"""
    code = models.CharField('Κωδικός', max_length=50, unique=True, blank=True,
                            help_text='Προγραμματικός κωδικός (π.χ. ANNUAL, SICK, BLOOD)')
    name = models.CharField('Όνομα Τύπου', max_length=100)
    description = models.TextField('Περιγραφή', blank=True)
    max_days = models.PositiveIntegerField('Μέγιστες Ημέρες', default=30)
    requires_approval = models.BooleanField('Απαιτεί Έγκριση από Προϊστάμενο', default=True)
    is_active = models.BooleanField('Ενεργός', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    subject_text = models.TextField('Κείμενο Θέματος', blank=True)
    decision_text = models.TextField('Κείμενο Απόφασης', blank=True)
    folder = models.CharField('Φ Φάκελος', max_length=255, blank=True)
    general_category = models.CharField('Γενική Κατηγορία Αδειών', max_length=100, blank=True)
    counts_against_balance = models.BooleanField('Μετράει σε Υπόλοιπο Αδειών', default=True,
        help_text='Αν είναι ενεργό, οι ημέρες αυτής της άδειας αφαιρούνται από το υπόλοιπο του χρήστη')
    affects_regular_leave_balance = models.BooleanField('Επηρεάζει Υπόλοιπο Κανονικών', default=True,
        help_text='Αν είναι ενεργό, η ολοκλήρωση αυτής της άδειας δημιουργεί εγγραφή στο ιστορικό υπολοίπου')
    id_adeias = models.CharField('Κωδικός Άδειας (ID Αδείας)', max_length=50, blank=True)
    name_simple = models.CharField('Απλό Όνομα', max_length=100, blank=True)
    is_simple = models.BooleanField('Απλή Άδεια', default=False,
        help_text='Για εορταστικές/προφορικές/επιμορφωτικές άδειες')
    thematic_folder = models.CharField('Θεματικός Φάκελος', max_length=255, blank=True)
    workflow_variant = models.CharField('Workflow Variant', max_length=30, default='STANDARD',
        help_text='STANDARD, KEDASY, SDEY - καθορίζει το approval path και τα rules')
    is_sick_leave_yd = models.BooleanField('Αναρρωτική Άδεια με ΥΔ', default=False,
        help_text='Αν είναι ενεργό, μετράει στο ετήσιο όριο αναρρωτικών με ΥΔ (2/έτος)')
    is_sick_leave_total = models.BooleanField('Σύνολο Αναρρωτικών', default=False,
        help_text='Αν είναι ενεργό, οι ημέρες μετράνε στο σύνολο αναρρωτικών του έτους (για alert Υγειονομικής Επιτροπής)')
    
    class Meta:
        verbose_name = 'Τύπος Άδειας'
        verbose_name_plural = 'Τύποι Αδειών'
        ordering = ['name']
    
    def __str__(self):
        return self.name


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
    
    ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx']
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
        ('PENDING_PROTOCOL', 'Για πρωτόκολλο ΠΔΕΔΕ'),
        ('IN_REVIEW', 'Σε επεξεργασία από τμήμα αδειών'),
        ('WAITING_FOR_DOCUMENTS', 'Σε αναμονή δικαιολογητικών'),
        ('DECISION_PREPARATION', 'Ετοιμασία απόφασης'),
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
    def can_be_edited(self):
        """Ελέγχει αν η αίτηση μπορεί να επεξεργαστεί"""
        return self.status == 'DRAFT'
    
    @property
    def can_be_approved_by_manager(self):
        """Ελέγχει αν η αίτηση μπορεί να εγκριθεί από προϊστάμενο"""
        return self.status == 'SUBMITTED'
    
    @property
    def can_be_processed(self):
        """Ελέγχει αν η αίτηση μπορεί να επεξεργαστεί από χειριστή"""
        return self.status in ['PENDING_PROTOCOL', 'WAITING_FOR_DOCUMENTS', 'IN_REVIEW']
    
    @property
    def is_pending(self):
        """Ελέγχει αν η αίτηση είναι εκκρεμής"""
        return self.status in ['SUBMITTED', 'PENDING_PROTOCOL', 'WAITING_FOR_DOCUMENTS', 'IN_REVIEW']
    
    @property
    def is_completed(self):
        """Ελέγχει αν η αίτηση έχει ολοκληρωθεί"""
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
        return self.status in ['SUBMITTED', 'PENDING_PROTOCOL']
    
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

            if self.leave_type.requires_approval:
                self.status = 'SUBMITTED'
            else:
                self.status = 'PENDING_PROTOCOL'
            self.submitted_at = timezone.now()
            self.save()
            return True
        return False
    
    def approve_by_manager(self, manager, comments=''):
        """Έγκριση από προϊστάμενο"""
        if self.can_be_approved_by_manager:
            self.status = 'PENDING_PROTOCOL'
            
            self.manager_approved_by = manager
            self.manager_approved_at = timezone.now()
            self.manager_comments = comments
            self.save()
            return True
        return False
    
    def reject_by_manager(self, manager, reason):
        """Απόρριψη από προϊστάμενο"""
        if self.can_be_approved_by_manager:
            self.status = 'SUPERVISOR_REJECTED'
            self.rejected_by = manager
            self.rejected_at = timezone.now()
            self.rejection_reason = reason
            self.save()
            return True
        return False
    
    def move_to_protocol(self):
        """Μεταφορά για πρωτόκολλο ΠΔΕΔΕ"""
        if self.status == 'PENDING_PROTOCOL':
            self.status = 'PENDING_PROTOCOL'
            self.save()
            return True
        return False
    
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
    
    def complete_by_handler(self, handler, comments=''):
        """Ολοκλήρωση αίτησης από χειριστή"""
        if self.status in ['PENDING_PROTOCOL', 'IN_REVIEW']:
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
            # Ενημέρωση leave balance
            self._update_leave_balance_on_completion()
            return True
        return False
    
    def _update_leave_balance_on_completion(self):
        """Ενημερώνει το leave balance όταν η αίτηση ολοκληρώνεται"""
        import logging
        logger = logging.getLogger(__name__)

        if self.status == 'COMPLETED':
            if self.leave_type.affects_regular_leave_balance:
                days_used = self.total_days
                if days_used > 0:
                    logger.info(f"Deducting {days_used} leave days for user {self.user} on completion of request {self.id}")
                    self.user.use_leave_days(days_used)

            if self.leave_type.is_sick_leave_total:
                self.user.sick_days_current_year = (self.user.sick_days_current_year or 0) + self.total_days
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
        if self.status in ['PENDING_PROTOCOL', 'IN_REVIEW', 'WAITING_FOR_DOCUMENTS']:
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
        return self.status in ['IN_REVIEW', 'DECISION_PREPARATION']

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
        
        # Οι προϊστάμενοι ΚΕΔΑΣΥ μπορούν να δουν και αιτήσεις από ΣΔΕΥ
        if (user.is_department_manager and
            user.department and user.department.department_type and
            user.department.department_type.code == 'KEDASY' and
            self.user.department and self.user.department.department_type and
            self.user.department.department_type.code == 'SDEY' and
            self.user.department.parent_department == user.department):
            return True
        
        # Οι χειριστές μπορούν να δουν όλες τις αιτήσεις
        if user.is_leave_handler:
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
        
        # Προϊστάμενοι μπορούν να εγκρίνουν αιτήσεις του τμήματός τους
        if user.is_department_manager and self.user.department == user.department and self.can_be_approved_by_manager:
            actions.extend(['approve', 'reject'])
        
        # Προϊστάμενοι ΚΕΔΑΣΥ μπορούν να εγκρίνουν αιτήσεις από ΣΔΕΥ
        if (user.is_department_manager and
            user.department and user.department.department_type and
            user.department.department_type.code == 'KEDASY' and
            self.user.department and self.user.department.department_type and
            self.user.department.department_type.code == 'SDEY' and
            self.user.department.parent_department == user.department and
            self.can_be_approved_by_manager):
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
    
    def is_kedasy_kepea_department(self):
        """Έλεγχος αν το τμήμα είναι ΚΕΔΑΣΥ, ΚΕΠΕΑ ή ΣΔΕΥ"""
        try:
            department = self.user.department
            if department and department.department_type:
                # Άμεσα τμήματα ΚΕΔΑΣΥ/ΚΕΠΕΑ
                if department.department_type.code in ['KEDASY', 'KEPEA']:
                    return True
                # ΣΔΕΥ που ανήκουν σε ΚΕΔΑΣΥ
                elif department.department_type.code == 'SDEY':
                    # Ελέγχουμε αν το γονικό τμήμα είναι ΚΕΔΑΣΥ
                    if (department.parent_department and
                        department.parent_department.department_type and
                        department.parent_department.department_type.code == 'KEDASY'):
                        return True
        except AttributeError:
            pass
        return False
    
    def can_add_kedasy_kepea_protocol(self, user):
        """Έλεγχος αν ο χρήστης μπορεί να προσθέσει πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ"""
        if not user.is_authenticated:
            return False
        
        # Έλεγχος αν είναι τμήμα ΚΕΔΑΣΥ/ΚΕΠΕΑ/ΣΔΕΥ
        if not self.is_kedasy_kepea_department():
            return False
        
        # Έλεγχος αν το status είναι PENDING_KEDASY_KEPEA_PROTOCOL
        if self.status != 'PENDING_PROTOCOL':
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
                elif department.department_type.code == 'SDEY':
                    if (department.parent_department and
                        department.parent_department.department_type and
                        department.parent_department.department_type.code == 'KEDASY'):
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
        
        # Αν δεν έχουν τεθεί τα πεδία έγκρισης προϊσταμένου (π.χ. για αναρρωτικές άδειες),
        # θέτουμε τα στοιχεία της έγκρισης τώρα
        if not self.manager_approved_by:
            self.manager_approved_by = user
            self.manager_approved_at = timezone.now()
            self.manager_comments = f"Αυτόματη έγκριση με πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ: {protocol_number}"
        
        self.status = 'PENDING_PROTOCOL'
        self.save()
        
        # Δημιουργία ιστορικού (αν υπάρχει το model)
        try:
            from .models import LeaveRequestHistory
            LeaveRequestHistory.objects.create(
                leave_request=self,
                action='KEDASY_KEPEA_PROTOCOL_ADDED',
                user=user,
                old_status='PENDING_PROTOCOL',
                new_status='PENDING_PROTOCOL',
                comments=f"Προστέθηκε πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ: {protocol_number}"
            )
        except ImportError:
            pass  # Το LeaveRequestHistory δεν υπάρχει ακόμα


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


class Letterhead(models.Model):
    """Επικεφαλίδα εγγράφων (PDF decisions) - editable από χειριστές"""
    header_text = models.TextField('Κείμενο Επικεφαλίδας',
        help_text='Υπουργείο, Διεύθυνση, Τμήμα - εμφανίζεται σε όλα τα PDF')
    address = models.CharField('Διεύθυνση', max_length=200, default='Ακτής Δυμαίων 25α, Πάτρα')
    postal_code = models.CharField('Ταχ. Κώδικας', max_length=10, default='26222')
    contact_info_template = models.CharField('Πρότυπο Πληροφοριών', max_length=200, blank=True,
        help_text='Πρότυπο για πληροφορίες επικοινωνίας')
    coat_of_arms = models.ImageField('Έμβλημα', upload_to='letterhead/', blank=True, null=True,
        help_text='Coat_of_arms_of_Greece.jpg')
    is_active = models.BooleanField('Ενεργή', default=True,
        help_text='Μόνο μία επικεφαλίδα μπορεί να είναι ενεργή')
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='Δημιουργήθηκε από')

    class Meta:
        verbose_name = 'Επικεφαλίδα Εγγράφου'
        verbose_name_plural = 'Επικεφαλίδες Εγγράφων'

    def __str__(self):
        return f"Επικεφαλίδα ({'Ενεργή' if self.is_active else 'Ανενεργή'})"

    def save(self, *args, **kwargs):
        """Αν ενεργοποιηθεί, απενεργοποίησε όλες τις άλλες"""
        if self.is_active:
            Letterhead.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_active(cls):
        """Επιστρέφει την ενεργή επικεφαλίδα"""
        return cls.objects.filter(is_active=True).first()


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
    is_finalized = models.BooleanField('Οριστικοποιημένο', default=False,
                                       help_text='Οριστικοποιημένες εγγραφές δεν τροποποιούνται')
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='verified_balance_entries',
                                    verbose_name='Επαληθεύτηκε από')
    verified_at = models.DateTimeField('Ημερομηνία Επαλήθευσης', null=True, blank=True)

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


# ============================================================
# Configuration models για KEDASY/SDEY variant architecture
# ============================================================

class WorkflowVariant(models.Model):
    """
    Παραμετροποιήσιμο workflow variant.
    Επιτρέπει την προσθήκη νέων ροών (STANDARD, KEDASY, SDEY)
    χωρίς αλλαγή στον βασικό κώδικα.
    """
    code = models.CharField('Κωδικός', max_length=30, unique=True,
                            help_text='STANDARD, KEDASY, SDEY')
    name = models.CharField('Όνομα', max_length=100)
    description = models.TextField('Περιγραφή', blank=True)
    requires_supervisor_approval = models.BooleanField('Απαιτεί Έγκριση Προϊσταμένου', default=True)
    is_active = models.BooleanField('Ενεργό', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)

    class Meta:
        verbose_name = 'Workflow Variant'
        verbose_name_plural = 'Workflow Variants'
        ordering = ['code']

    def __str__(self):
        return f"{self.name} ({self.code})"


class ApprovalRule(models.Model):
    """
    Κανόνας έγκρισης ανά workflow variant και τύπο τμήματος.
    Καθορίζει ποιος εγκρίνει και με ποια σειρά.
    """
    APPROVER_ROLES = [
        ('DEPT_MANAGER', 'Προϊστάμενος Τμήματος'),
        ('KEDASY_HEAD', 'Προϊστάμενος ΚΕΔΑΣΥ'),
        ('LEAVE_HANDLER', 'Χειριστής Αδειών'),
        ('REGIONAL_DIRECTOR', 'Περιφερειακός Διευθυντής'),
    ]

    workflow_variant = models.ForeignKey(WorkflowVariant, on_delete=models.CASCADE,
                                         related_name='approval_rules',
                                         verbose_name='Workflow Variant')
    department_type_code = models.CharField('Τύπος Τμήματος', max_length=30, blank=True,
                                            help_text='Αφήστε κενό για όλους τους τύπους')
    approver_role = models.CharField('Ρόλος Εγκρίνοντα', max_length=30, choices=APPROVER_ROLES)
    approval_order = models.PositiveIntegerField('Σειρά Έγκρισης', default=1,
                                                  help_text='1 = πρώτος εγκρίνων, 2 = δεύτερος, κλπ')
    is_active = models.BooleanField('Ενεργό', default=True)

    class Meta:
        verbose_name = 'Κανόνας Έγκρισης'
        verbose_name_plural = 'Κανόνες Έγκρισης'
        ordering = ['workflow_variant', 'department_type_code', 'approval_order']

    def __str__(self):
        return f"{self.workflow_variant} → {self.get_approver_role_display()} ({self.approval_order})"


class RequiredAttachmentRule(models.Model):
    """
    Κανόνας απαιτούμενων συνημμένων ανά workflow variant και τύπο άδειας.
    """
    workflow_variant = models.ForeignKey(WorkflowVariant, on_delete=models.CASCADE,
                                         related_name='attachment_rules',
                                         verbose_name='Workflow Variant')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='attachment_rules',
                                   verbose_name='Τύπος Άδειας')
    attachment_name = models.CharField('Όνομα Συνημμένου', max_length=200)
    description = models.TextField('Περιγραφή', blank=True)
    is_required = models.BooleanField('Υποχρεωτικό', default=True)
    is_active = models.BooleanField('Ενεργό', default=True)

    class Meta:
        verbose_name = 'Κανόνας Συνημμένου'
        verbose_name_plural = 'Κανόνες Συνημμένων'
        ordering = ['workflow_variant', 'leave_type', 'attachment_name']

    def __str__(self):
        lt = self.leave_type.name if self.leave_type else 'Όλοι'
        return f"{self.workflow_variant} / {lt} → {self.attachment_name}"


class DecisionTemplate(models.Model):
    """
    Template απόφασης ανά workflow variant και τύπο άδειας.
    """
    workflow_variant = models.ForeignKey(WorkflowVariant, on_delete=models.CASCADE,
                                         related_name='decision_templates',
                                         verbose_name='Workflow Variant')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, null=True, blank=True,
                                   related_name='decision_templates',
                                   verbose_name='Τύπος Άδειας')
    template_file = models.FileField('Αρχείο Template', upload_to='decision_templates/',
                                     blank=True, null=True)
    header_text = models.TextField('Κείμενο Επικεφαλίδας', blank=True,
                                    help_text='Αντικαθιστά το default header')
    subject_text = models.TextField('Κείμενο Θέματος', blank=True,
                                     help_text='Αντικαθιστά το default subject')
    decision_body_template = models.TextField('Πρότυπο Σώματος Απόφασης', blank=True,
                                               help_text='Jinja2/Django template body')
    is_active = models.BooleanField('Ενεργό', default=True)

    class Meta:
        verbose_name = 'Template Απόφασης'
        verbose_name_plural = 'Templates Αποφάσεων'
        ordering = ['workflow_variant', 'leave_type']

    def __str__(self):
        lt = self.leave_type.name if self.leave_type else 'Όλοι'
        return f"{self.workflow_variant} / {lt}"
