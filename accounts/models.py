from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Custom user manager για email authentication"""
    
    def create_user(self, email, first_name, last_name, password=None, **extra_fields):
        if not email:
            raise ValueError('Το email είναι υποχρεωτικό')
        
        # Για νέους χρήστες, default κατάσταση είναι PENDING και inactive
        # εκτός αν ρητά καθορίζεται διαφορετικά
        extra_fields.setdefault('registration_status', 'PENDING')
        extra_fields.setdefault('is_active', False)
        
        email = self.normalize_email(email)
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            **extra_fields
        )
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, first_name, last_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        
        # Superusers bypass registration approval workflow
        extra_fields.setdefault('registration_status', 'APPROVED')
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, first_name, last_name, password, **extra_fields)


class Prefecture(models.Model):
    """Μοντέλο για τους νομούς"""
    
    code = models.CharField('Κωδικός Νομού', max_length=50, unique=True)
    name = models.CharField('Όνομα Νομού', max_length=100)
    is_active = models.BooleanField('Ενεργός', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Νομός'
        verbose_name_plural = 'Νομοί'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Headquarters(models.Model):
    """Μοντέλο για τις έδρες"""
    
    code = models.CharField('Κωδικός Έδρας', max_length=50, unique=True)
    name = models.CharField('Όνομα Έδρας', max_length=100)
    is_active = models.BooleanField('Ενεργή', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Έδρα'
        verbose_name_plural = 'Έδρες'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Department(models.Model):
    """Μοντέλο για τα Τμήματα/Γραφεία της ΠΔΕΔΕ"""
    
    DEPARTMENT_TYPES = [
        ('DIRECTION', 'Διεύθυνση'),
        ('AUTONOMOUS_DIRECTION', 'Αυτοτελής Διεύθυνση'),
        ('DEPARTMENT', 'Τμήμα'),
        ('OFFICE', 'Γραφείο'),
        ('VIRTUAL_DEPARTMENT', 'Εικονικό Τμήμα'),
    ]
    
    name = models.CharField('Όνομα Τμήματος', max_length=200)
    code = models.CharField('Κωδικός Τμήματος', max_length=50, unique=True)
    department_type = models.CharField('Τύπος Τμήματος', max_length=30, choices=DEPARTMENT_TYPES)
    parent_department = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                                        verbose_name='Γονικό Τμήμα')
    prefecture = models.ForeignKey(Prefecture, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='Νομός', related_name='departments')
    headquarters = models.ForeignKey(Headquarters, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='Έδρα', related_name='departments')
    is_active = models.BooleanField('Ενεργό', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Τμήμα'
        verbose_name_plural = 'Τμήματα'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_all_sub_departments(self):
        """Επιστρέφει όλα τα υποτμήματα (άμεσα και έμμεσα)"""
        sub_departments = [self]  # Συμπεριλαμβάνω και το ίδιο το τμήμα
        
        # Βρίσκω τα άμεσα παιδιά
        direct_children = Department.objects.filter(parent_department=self)
        
        # Για κάθε άμεσο παιδί, βρίσκω και τα δικά του παιδιά (αναδρομικά)
        for child in direct_children:
            sub_departments.extend(child.get_all_sub_departments())
        
        return sub_departments

    def get_department_manager(self):
        """Επιστρέφει τον προϊστάμενο του τμήματος"""
        return self.users.filter(roles__code='department_manager').first()


class Role(models.Model):
    """Μοντέλο για τους ρόλους χρηστών"""
    
    code = models.CharField('Κωδικός Ρόλου', max_length=30, unique=True)
    name = models.CharField('Όνομα Ρόλου', max_length=100)
    description = models.TextField('Περιγραφή', blank=True)
    is_active = models.BooleanField('Ενεργός', default=True)
    
    class Meta:
        verbose_name = 'Ρόλος'
        verbose_name_plural = 'Ρόλοι'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Specialty(models.Model):
    """Μοντέλο για τις ειδικότητες χρηστών"""
    
    specialties_full = models.CharField('Πλήρης Ειδικότητα', max_length=200, unique=True)
    specialties_short = models.CharField('Σύντομη Ειδικότητα', max_length=50)
    is_active = models.BooleanField('Ενεργή', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Ειδικότητα'
        verbose_name_plural = 'Ειδικότητες'
        ordering = ['specialties_short', 'specialties_full']
    
    def __str__(self):
        return self.specialties_full
    
    def save(self, *args, **kwargs):
        """Αυτόματη εξαγωγή του σύντομου κωδικού από το πλήρες όνομα"""
        if self.specialties_full and not self.specialties_short:
            # Εξαγωγή μέχρι την πρώτη παύλα (-)
            if ' - ' in self.specialties_full:
                self.specialties_short = self.specialties_full.split(' - ')[0].strip()
            else:
                self.specialties_short = self.specialties_full[:10]  # Fallback
        super().save(*args, **kwargs)


class User(AbstractUser):
    """Επεκτεταμένο μοντέλο χρήστη"""
    
    USER_CATEGORIES = [
        ('ADMINISTRATIVE', 'Διοικητικοί'),
        ('EDUCATIONAL', 'Εκπαιδευτικοί'),
        ('SUBSTITUTE', 'Αναπληρωτές'),
        ('OTHER', 'Άλλο'),
    ]
    
    REGISTRATION_STATUS_CHOICES = [
        ('PENDING', 'Εκκρεμεί Έγκριση'),
        ('APPROVED', 'Εγκεκριμένος'),
        ('REJECTED', 'Απορριφθείς'),
    ]
    
    # Προσωπικά στοιχεία
    first_name = models.CharField('Όνομα', max_length=50)
    last_name = models.CharField('Επίθετο', max_length=50)
    email = models.EmailField('Email', unique=True)
    phone = models.CharField('Τηλέφωνο', max_length=15, blank=True)
    GENDER_CHOICES = [
        ('MALE', 'Άνδρας'),
        ('FEMALE', 'Γυναίκα'),
        ('OTHER', 'Άλλο'),
    ]
    gender = models.CharField('Φύλο', max_length=10, choices=GENDER_CHOICES, blank=True)
    
    # Υπηρεσιακά στοιχεία
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='Τμήμα', related_name='users')
    roles = models.ManyToManyField(Role, verbose_name='Ρόλοι', blank=True, related_name='users')
    user_category = models.CharField('Κατηγορία Χρήστη', max_length=20, choices=USER_CATEGORIES,
                                   default='OTHER', blank=True)
    specialty = models.ForeignKey(Specialty, on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name='Ειδικότητα', related_name='users')
    
    # Επιπλέον στοιχεία χρήστη
    notification = models.TextField('Κοινοποίηση Απόφασης', blank=True,
                                  help_text='Υπηρεσίες που θα γίνει κοινοποίηση η απόφαση της άδειας')
    user_description = models.TextField('Περιγραφή Χρήστη', blank=True,
                                      help_text='Ιδιότητα του χρήστη')
    
    # Κατάσταση εγγραφής
    registration_status = models.CharField('Κατάσταση Εγγραφής', max_length=20,
                                         choices=REGISTRATION_STATUS_CHOICES,
                                         default='PENDING')
    registration_date = models.DateTimeField('Ημερομηνία Εγγραφής', auto_now_add=True)
    approved_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                  verbose_name='Εγκρίθηκε από', related_name='approved_users')
    approval_date = models.DateTimeField('Ημερομηνία Έγκρισης', null=True, blank=True)
    approval_notes = models.TextField('Σημειώσεις Έγκρισης', blank=True)
    
    # Ημερομηνίες
    hire_date = models.DateField('Ημερομηνία Πρόσληψης', null=True, blank=True)
    is_active = models.BooleanField('Ενεργός', default=True)
    
    # Django fields - χρησιμοποιούμε email ως username για SSO
    username = None  # Αφαιρούμε το username field εντελώς
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    # Custom manager
    objects = UserManager()
    
    class Meta:
        verbose_name = 'Χρήστης'
        verbose_name_plural = 'Χρήστες'
        ordering = ['last_name', 'first_name']
    
    def __str__(self):
        return f"{self.last_name} {self.first_name}"
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    @property
    def is_department_manager(self):
        return self.roles.filter(code='MANAGER').exists()
    
    @property
    def is_leave_handler(self):
        return self.roles.filter(code='HR_OFFICER').exists()
    
    @property
    def is_administrator(self):
        return self.roles.filter(code='administrator').exists()
    
    @property
    def is_employee(self):
        return self.roles.filter(code='EMPLOYEE').exists()
    
    @property
    def manager(self):
        """Επιστρέφει τον προϊστάμενο βάσει του τμήματος"""
        if self.department:
            return self.department.get_department_manager()
        return None
    
    def can_approve_leaves(self):
        """Μπορεί να εγκρίνει αιτήσεις αδειών"""
        return self.roles.filter(code__in=['MANAGER', 'HR_OFFICER', 'administrator']).exists()
    
    def get_subordinates(self):
        """Επιστρέφει τους υφισταμένους του χρήστη"""
        if self.is_department_manager and self.department:
            # Χρήστες από το ίδιο τμήμα που δεν είναι προϊστάμενοι
            return User.objects.filter(
                department=self.department,
                is_active=True
            ).exclude(roles__code='MANAGER')
        return User.objects.none()

    def get_role_names(self):
        """Επιστρέφει τα ονόματα των ρόλων του χρήστη"""
        return ', '.join(self.roles.values_list('name', flat=True))

    def add_role(self, role_code):
        """Προσθέτει ρόλο στον χρήστη"""
        try:
            role = Role.objects.get(code=role_code)
            self.roles.add(role)
            return True
        except Role.DoesNotExist:
            return False

    def remove_role(self, role_code):
        """Αφαιρεί ρόλο από τον χρήστη"""
        try:
            role = Role.objects.get(code=role_code)
            self.roles.remove(role)
            return True
        except Role.DoesNotExist:
            return False

    def has_role(self, role_code):
        """Ελέγχει αν ο χρήστης έχει συγκεκριμένο ρόλο"""
        return self.roles.filter(code=role_code).exists()

    def get_user_category_display(self):
        """Επιστρέφει την ελληνική ονομασία της κατηγορίας χρήστη"""
        return dict(self.USER_CATEGORIES).get(self.user_category, self.user_category)
    
    def get_registration_status_display(self):
        """Επιστρέφει την ελληνική ονομασία της κατάστασης εγγραφής"""
        return dict(self.REGISTRATION_STATUS_CHOICES).get(self.registration_status, self.registration_status)
    
    @property
    def is_pending_approval(self):
        """Επιστρέφει True αν η εγγραφή είναι σε αναμονή έγκρισης"""
        return self.registration_status == 'PENDING'
    
    @property
    def is_approved(self):
        """Επιστρέφει True αν η εγγραφή έχει εγκριθεί"""
        return self.registration_status == 'APPROVED'
    
    @property
    def is_rejected(self):
        """Επιστρέφει True αν η εγγραφή έχει απορριφθεί"""
        return self.registration_status == 'REJECTED'
    
    def approve_registration(self, approved_by_user, notes=''):
        """Εγκρίνει την εγγραφή του χρήστη"""
        from django.utils import timezone
        self.registration_status = 'APPROVED'
        self.approved_by = approved_by_user
        self.approval_date = timezone.now()
        self.approval_notes = notes
        self.is_active = True  # Ενεργοποίηση του χρήστη
        self.save()
    
    def reject_registration(self, rejected_by_user, notes=''):
        """Απορρίπτει την εγγραφή του χρήστη"""
        from django.utils import timezone
        self.registration_status = 'REJECTED'
        self.approved_by = rejected_by_user
        self.approval_date = timezone.now()
        self.approval_notes = notes
        self.is_active = False  # Απενεργοποίηση του χρήστη
        self.save()
    
    def can_access_system(self):
        """Ελέγχει αν ο χρήστης μπορεί να έχει πρόσβαση στο σύστημα"""
        return self.is_superuser or (self.is_approved and self.is_active)
