from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta

User = get_user_model()


class LeaveType(models.Model):
    """Τύποι Αδειών"""
    
    name = models.CharField('Όνομα Τύπου Άδειας', max_length=100)
    code = models.CharField('Κωδικός', max_length=20, unique=True)
    description = models.TextField('Περιγραφή', blank=True)
    max_days_per_year = models.PositiveIntegerField('Μέγιστες Ημέρες/Έτος', null=True, blank=True)
    requires_documents = models.BooleanField('Απαιτεί Δικαιολογητικά', default=False)
    logic_handler = models.CharField('Χειριστής Λογικής', max_length=50, default='default')
    is_active = models.BooleanField('Ενεργός', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Τύπος Άδειας'
        verbose_name_plural = 'Τύποι Αδειών'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class LeaveRequest(models.Model):
    """Αιτήσεις Αδειών"""
    
    STATUS_CHOICES = [
        ('SUBMITTED', 'Υποβλήθηκε'),
        ('APPROVED_MANAGER', 'Εγκρίθηκε από Προϊστάμενο'),
        ('FOR_PROTOCOL_PDEDE', 'Για Πρωτόκολλο ΠΔΕΔΕ'),
        ('UNDER_PROCESSING', 'Προς Επεξεργασία'),
        ('APPROVED', 'Εγκρίθηκε'),
        ('COMPLETED', 'Ολοκληρώθηκε'),
        ('REJECTED_MANAGER', 'Απορρίφθηκε από Προϊστάμενο'),
        ('REJECTED_OPERATOR', 'Απορρίφθηκε από Χειριστή'),
    ]
    
    # Βασικά στοιχεία αίτησης
    employee = models.ForeignKey(User, on_delete=models.CASCADE, 
                               verbose_name='Υπάλληλος', related_name='leave_requests')
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, 
                                 verbose_name='Τύπος Άδειας')
    
    # Ημερομηνίες άδειας
    start_date = models.DateField('Ημερομηνία Έναρξης')
    end_date = models.DateField('Ημερομηνία Λήξης')
    total_days = models.PositiveIntegerField('Συνολικές Ημέρες', default=0)
    
    # Περιγραφή/Αιτιολογία
    description = models.TextField('Περιγραφή/Αιτιολογία', blank=True)
    
    # Κατάσταση και workflow
    status = models.CharField('Κατάσταση', max_length=30, choices=STATUS_CHOICES, default='SUBMITTED')
    protocol_number = models.CharField('Αριθμός Πρωτοκόλλου', max_length=50, blank=True)
    
    # Εγκρίσεις και επεξεργασία
    manager_approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='manager_approvals',
                                          verbose_name='Εγκρίθηκε από Προϊστάμενο')
    manager_approved_at = models.DateTimeField('Ημερομηνία Έγκρισης Προϊσταμένου', null=True, blank=True)
    manager_comments = models.TextField('Σχόλια Προϊσταμένου', blank=True)
    
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='processed_requests',
                                   verbose_name='Επεξεργάστηκε από')
    processed_at = models.DateTimeField('Ημερομηνία Επεξεργασίας', null=True, blank=True)
    processing_comments = models.TextField('Σχόλια Επεξεργασίας', blank=True)
    
    # Χρονικές σφραγίδες
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    updated_at = models.DateTimeField('Ημερομηνία Ενημέρωσης', auto_now=True)
    
    # Απόρριψη
    rejected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='rejected_requests',
                                  verbose_name='Απορρίφθηκε από')
    rejected_at = models.DateTimeField('Ημερομηνία Απόρριψης', null=True, blank=True)
    rejection_reason = models.TextField('Αιτιολογία Απόρριψης', blank=True)
    
    class Meta:
        verbose_name = 'Αίτηση Άδειας'
        verbose_name_plural = 'Αιτήσεις Αδειών'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.employee.full_name} - {self.leave_type.name} ({self.start_date.strftime('%d/%m/%Y')} - {self.end_date.strftime('%d/%m/%Y')})"
    
    def clean(self):
        """Επικύρωση δεδομένων"""
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValidationError('Η ημερομηνία έναρξης δεν μπορεί να είναι μεταγενέστερη της ημερομηνίας λήξης.')
            
            if self.start_date < timezone.now().date():
                raise ValidationError('Η ημερομηνία έναρξης δεν μπορεί να είναι στο παρελθόν.')
    
    def save(self, *args, **kwargs):
        # Υπολογισμός συνολικών ημερών
        if self.start_date and self.end_date:
            delta = self.end_date - self.start_date
            self.total_days = delta.days + 1  # +1 για να συμπεριλάβουμε και τις δύο ημερομηνίες
        
        super().save(*args, **kwargs)
    
    @property
    def status_display_greek(self):
        """Επιστρέφει την κατάσταση στα ελληνικά"""
        status_dict = dict(self.STATUS_CHOICES)
        return status_dict.get(self.status, self.status)
    
    @property
    def can_be_approved_by_manager(self):
        """Μπορεί να εγκριθεί από προϊστάμενο"""
        return self.status == 'SUBMITTED'
    
    @property
    def can_be_rejected_by_manager(self):
        """Μπορεί να απορριφθεί από προϊστάμενο"""
        return self.status == 'SUBMITTED'
    
    @property
    def can_be_processed(self):
        """Μπορεί να επεξεργαστεί από χειριστή"""
        return self.status == 'APPROVED_MANAGER'
    
    @property
    def can_be_completed(self):
        """Μπορεί να ολοκληρωθεί"""
        return self.status in ['APPROVED_MANAGER', 'UNDER_PROCESSING']
    
    @property
    def is_pending(self):
        """Είναι σε εκκρεμότητα"""
        return self.status in ['SUBMITTED', 'APPROVED_MANAGER', 'FOR_PROTOCOL_PDEDE', 'UNDER_PROCESSING']
    
    @property
    def is_completed(self):
        """Έχει ολοκληρωθεί"""
        return self.status == 'COMPLETED'
    
    @property
    def is_rejected(self):
        """Έχει απορριφθεί"""
        return self.status in ['REJECTED_MANAGER', 'REJECTED_OPERATOR']
    
    def approve_by_manager(self, manager, comments=''):
        """Έγκριση από προϊστάμενο"""
        if not self.can_be_approved_by_manager:
            raise ValidationError('Αυτή η αίτηση δεν μπορεί να εγκριθεί από προϊστάμενο.')
        
        self.status = 'APPROVED_MANAGER'
        self.manager_approved_by = manager
        self.manager_approved_at = timezone.now()
        self.manager_comments = comments
        self.save()
    
    def reject_by_manager(self, manager, reason=''):
        """Απόρριψη από προϊστάμενο"""
        if not self.can_be_rejected_by_manager:
            raise ValidationError('Αυτή η αίτηση δεν μπορεί να απορριφθεί από προϊστάμενο.')
        
        self.status = 'REJECTED_MANAGER'
        self.rejected_by = manager
        self.rejected_at = timezone.now()
        self.rejection_reason = reason
        self.save()
    
    def complete_by_handler(self, handler, comments=''):
        """Ολοκλήρωση από χειριστή"""
        if not self.can_be_completed:
            raise ValidationError('Αυτή η αίτηση δεν μπορεί να ολοκληρωθεί.')
        
        self.status = 'COMPLETED'
        self.processed_by = handler
        self.processed_at = timezone.now()
        self.processing_comments = comments
        self.save()
    
    def reject_by_handler(self, handler, reason=''):
        """Απόρριψη από χειριστή"""
        if not self.can_be_processed:
            raise ValidationError('Αυτή η αίτηση δεν μπορεί να απορριφθεί από χειριστή.')
        
        self.status = 'REJECTED_OPERATOR'
        self.rejected_by = handler
        self.rejected_at = timezone.now()
        self.rejection_reason = reason
        self.save()


class LeaveRequestDocument(models.Model):
    """Δικαιολογητικά Αιτήσεων Αδειών"""
    
    leave_request = models.ForeignKey(LeaveRequest, on_delete=models.CASCADE, 
                                    related_name='documents',
                                    verbose_name='Αίτηση Άδειας')
    document = models.FileField('Αρχείο', upload_to='leave_documents/%Y/%m/')
    description = models.CharField('Περιγραφή', max_length=200, blank=True)
    uploaded_at = models.DateTimeField('Ημερομηνία Μεταφόρτωσης', auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, 
                                  verbose_name='Μεταφορτώθηκε από')
    
    class Meta:
        verbose_name = 'Δικαιολογητικό Άδειας'
        verbose_name_plural = 'Δικαιολογητικά Αδειών'
    
    def __str__(self):
        return f"{self.leave_request} - {self.description or 'Δικαιολογητικό'}"