import os
import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import FileExtensionValidator
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericRelation
from notifications.models import Notification

User = get_user_model()


class Department(models.Model):
    """Τμήμα/Υπηρεσία"""
    name = models.CharField('Όνομα Τμήματος', max_length=200)
    code = models.CharField('Κωδικός Τμήματος', max_length=50, unique=True)
    is_active = models.BooleanField('Ενεργό', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Τμήμα'
        verbose_name_plural = 'Τμήματα'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class LeaveType(models.Model):
    """Τύπος άδειας"""
    name = models.CharField('Όνομα Τύπου', max_length=100)
    description = models.TextField('Περιγραφή', blank=True)
    max_days = models.PositiveIntegerField('Μέγιστες Ημέρες', default=30)
    requires_approval = models.BooleanField('Απαιτεί Έγκριση', default=True)
    is_active = models.BooleanField('Ενεργός', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    subject_text = models.TextField('Κείμενο Θέματος', blank=True)
    decision_text = models.TextField('Κείμενο Απόφασης', blank=True)
    folder = models.CharField('Φ Φάκελος', max_length=255, blank=True)
    general_category = models.CharField('Γενική Κατηγορία Αδειών', max_length=100, blank=True)
    
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
    
    ALLOWED_EXTENSIONS = ['pdf', 'jpg', 'jpeg', 'png']
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
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
        ('DRAFT', 'Προσχέδιο'),
        ('SUBMITTED', 'Υποβλήθηκε'),
        ('APPROVED_MANAGER', 'Εγκρίθηκε από Προϊστάμενο'),
        ('REJECTED_MANAGER', 'Απορρίφθηκε από Προϊστάμενο'),
        ('FOR_PROTOCOL_PDEDE', 'Για Πρωτόκολλο ΠΔΕΔΕ'),
        ('UNDER_PROCESSING', 'Προς Επεξεργασία'),
        ('COMPLETED', 'Ολοκληρώθηκε'),
        ('REJECTED_OPERATOR', 'Απορρίφθηκε από Χειριστή'),
    ]
    
    # Βασικά πεδία
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leave_requests', verbose_name='Χρήστης')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, verbose_name='Τύπος Άδειας')
    description = models.TextField('Περιγραφή/Αιτιολογία', blank=True)
    
    # Στάτους και ημερομηνίες
    status = models.CharField('Κατάσταση', max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    updated_at = models.DateTimeField('Ημερομηνία Ενημέρωσης', auto_now=True)
    submitted_at = models.DateTimeField('Ημερομηνία Υποβολής', null=True, blank=True)
    
    # Έγκριση από προϊστάμενο
    manager_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                          related_name='approved_leaves', verbose_name='Εγκρίθηκε από Προϊστάμενο')
    manager_approved_at = models.DateTimeField('Ημερομηνία Έγκρισης Προϊσταμένου', null=True, blank=True)
    manager_comments = models.TextField('Σχόλια Προϊσταμένου', blank=True)
    
    # Επεξεργασία από χειριστή
    protocol_number = models.CharField('Αριθμός Πρωτοκόλλου', max_length=100, blank=True)
    protocol_pdf_path = models.CharField('Διαδρομή Πρωτοκολλημένου PDF', max_length=500, blank=True)
    protocol_pdf_encryption_key = models.CharField('Κλειδί Κρυπτογράφησης Πρωτοκόλλου', max_length=64, blank=True)
    protocol_pdf_size = models.PositiveIntegerField('Μέγεθος Πρωτοκολλημένου PDF', null=True, blank=True)
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
    
    # Notifications
    notifications = GenericRelation(Notification)
    
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
        return self.status in ['DRAFT', 'SUBMITTED']
    
    @property
    def can_be_approved_by_manager(self):
        """Ελέγχει αν η αίτηση μπορεί να εγκριθεί από προϊστάμενο"""
        return self.status == 'SUBMITTED'
    
    @property
    def can_be_processed(self):
        """Ελέγχει αν η αίτηση μπορεί να επεξεργαστεί από χειριστή"""
        return self.status in ['APPROVED_MANAGER', 'FOR_PROTOCOL_PDEDE']
    
    @property
    def is_pending(self):
        """Ελέγχει αν η αίτηση είναι εκκρεμής"""
        return self.status in ['SUBMITTED', 'APPROVED_MANAGER', 'FOR_PROTOCOL_PDEDE', 'UNDER_PROCESSING']
    
    @property
    def is_completed(self):
        """Ελέγχει αν η αίτηση έχει ολοκληρωθεί"""
        return self.status == 'COMPLETED'
    
    @property
    def is_rejected(self):
        """Ελέγχει αν η αίτηση έχει απορριφθεί"""
        return self.status in ['REJECTED_MANAGER', 'REJECTED_OPERATOR']
    
    def submit(self):
        """Υποβολή αίτησης"""
        if self.status == 'DRAFT':
            self.status = 'SUBMITTED'
            self.submitted_at = timezone.now()
            self.save()
            return True
        return False
    
    def approve_by_manager(self, manager, comments=''):
        """Έγκριση από προϊστάμενο"""
        if self.can_be_approved_by_manager:
            self.status = 'APPROVED_MANAGER'
            self.manager_approved_by = manager
            self.manager_approved_at = timezone.now()
            self.manager_comments = comments
            self.save()
            return True
        return False
    
    def reject_by_manager(self, manager, reason):
        """Απόρριψη από προϊστάμενο"""
        if self.can_be_approved_by_manager:
            self.status = 'REJECTED_MANAGER'
            self.rejected_by = manager
            self.rejected_at = timezone.now()
            self.rejection_reason = reason
            self.save()
            return True
        return False
    
    def move_to_protocol(self):
        """Μεταφορά για πρωτόκολλο ΠΔΕΔΕ"""
        if self.status == 'APPROVED_MANAGER':
            self.status = 'FOR_PROTOCOL_PDEDE'
            self.save()
            return True
        return False
    
    def start_processing(self, handler, protocol_number='', comments=''):
        """Έναρξη επεξεργασίας από χειριστή"""
        if self.can_be_processed:
            self.status = 'UNDER_PROCESSING'
            self.processed_by = handler
            self.processed_at = timezone.now()
            if protocol_number:
                self.protocol_number = protocol_number
            self.processing_comments = comments
            self.save()
            return True
        return False
    
    def complete(self):
        """Ολοκλήρωση αίτησης"""
        if self.status == 'UNDER_PROCESSING':
            self.status = 'COMPLETED'
            self.completed_at = timezone.now()
            self.save()
            return True
        return False
    
    def complete_by_handler(self, handler, comments=''):
        """Ολοκλήρωση αίτησης από χειριστή"""
        if self.status in ['APPROVED_MANAGER', 'FOR_PROTOCOL_PDEDE', 'UNDER_PROCESSING']:
            self.status = 'COMPLETED'
            self.completed_at = timezone.now()
            self.processed_by = handler
            self.processed_at = timezone.now()
            if comments:
                self.processing_comments = comments
            self.save()
            return True
        return False
    
    def reject_by_operator(self, operator, reason):
        """Απόρριψη από χειριστή"""
        if self.status in ['FOR_PROTOCOL_PDEDE', 'UNDER_PROCESSING']:
            self.status = 'REJECTED_OPERATOR'
            self.rejected_by = operator
            self.rejected_at = timezone.now()
            self.rejection_reason = reason
            self.save()
            return True
        return False
    
    def reject_by_handler(self, handler, reason):
        """Απόρριψη από χειριστή"""
        if self.status in ['APPROVED_MANAGER', 'FOR_PROTOCOL_PDEDE', 'UNDER_PROCESSING']:
            self.status = 'REJECTED_OPERATOR'
            self.rejected_by = handler
            self.rejected_at = timezone.now()
            self.rejection_reason = reason
            self.save()
            return True
        return False
    
    @property
    def has_protocol_pdf(self):
        """Ελέγχει αν υπάρχει πρωτοκολλημένο PDF"""
        return bool(self.protocol_pdf_path and self.protocol_pdf_encryption_key)
        return False
    
    def has_protocol_pdf(self):
        """Επιστρέφει True αν υπάρχει πρωτοκολλημένο PDF"""
        return bool(self.protocol_pdf_path and self.protocol_pdf_encryption_key)
    
    def get_protocol_pdf_url(self):
        """URL για το πρωτοκολλημένο PDF"""
        if self.has_protocol_pdf():
            from django.urls import reverse
            return reverse('leaves:serve_protocol_pdf', kwargs={'pk': self.pk})
        return None
    
    def get_status_display_class(self):
        """CSS κλάση για το status badge"""
        status_classes = {
            'DRAFT': 'secondary',
            'SUBMITTED': 'warning',
            'APPROVED_MANAGER': 'info',
            'REJECTED_MANAGER': 'danger',
            'FOR_PROTOCOL_PDEDE': 'secondary',
            'UNDER_PROCESSING': 'primary',
            'COMPLETED': 'success',
            'REJECTED_OPERATOR': 'danger',
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
        
        # Οι χειριστές μπορούν να δουν όλες τις αιτήσεις
        if user.is_leave_handler:
            return True
        
        return False
    
    def get_next_actions(self, user):
        """Επιστρέφει τις επόμενες δυνατές ενέργειες για τον χρήστη"""
        actions = []
        
        if self.user == user and self.can_be_edited:
            actions.append('edit')
        
        if user.is_department_manager and self.user.department == user.department and self.can_be_approved_by_manager:
            actions.extend(['approve', 'reject'])
        
        if user.is_leave_handler and self.can_be_processed:
            actions.extend(['process', 'reject'])
        
        if user.is_leave_handler and self.status == 'UNDER_PROCESSING':
            actions.append('complete')
        
        return actions


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
