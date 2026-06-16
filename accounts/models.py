from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


def convert_first_name_to_accusative(name):
    if not name:
        return name
    if name.endswith('ας'):
        return name[:-2] + 'α'
    elif name.endswith('ης'):
        return name[:-2] + 'η'
    elif name.endswith('ος'):
        return name[:-2] + 'ο'
    elif name.endswith('ες'):
        return name[:-2] + 'η'
    return name

def convert_last_name_to_accusative(surname):
    if not surname:
        return surname
    if surname.endswith('ας'):
        return surname[:-2] + 'α'
    elif surname.endswith('ης'):
        return surname[:-2] + 'η'
    elif surname.endswith('ος'):
        return surname[:-2] + 'ο'
    elif surname.endswith('ου'):
        return surname
    return surname


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


class DepartmentType(models.Model):
    """Μοντέλο για τους τύπους τμημάτων"""
    
    code = models.CharField('Κωδικός Τύπου', max_length=30, unique=True)
    name = models.CharField('Όνομα Τύπου', max_length=100)
    description = models.TextField('Περιγραφή', blank=True)
    is_active = models.BooleanField('Ενεργός', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Τύπος Τμήματος'
        verbose_name_plural = 'Τύποι Τμημάτων'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Department(models.Model):
    """Μοντέλο για τα Τμήματα/Γραφεία της ΠΔΕΔΕ"""
    
    name = models.CharField('Όνομα Τμήματος', max_length=200)
    code = models.CharField('Κωδικός Τμήματος', max_length=50, unique=True)
    department_type = models.ForeignKey(DepartmentType, on_delete=models.PROTECT,
                                      verbose_name='Τύπος Τμήματος', related_name='departments')
    parent_department = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True,
                                        verbose_name='Γονικό Τμήμα')
    prefecture = models.ForeignKey(Prefecture, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='Νομός', related_name='departments')
    headquarters = models.ForeignKey(Headquarters, on_delete=models.SET_NULL, null=True, blank=True,
                                   verbose_name='Έδρα', related_name='departments')
    manager = models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name='Προϊστάμενος Τμήματος', related_name='managed_departments')
    is_virtual = models.BooleanField('Εικονικό Τμήμα', default=False,
                                     help_text='True για ΣΔΕΥ - κληρονομούν προϊστάμενο από το γονικό ΚΕΔΑΣΥ')
    is_active = models.BooleanField('Ενεργό', default=True)
    has_atypical_leaves = models.BooleanField('Άτυπες Άδειες', default=False,
        help_text='Τα τμήματα που χειρίζονται άτυπες άδειες (π.χ. εκπαιδευτικοί)')
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
        # Πρώτα ελέγχουμε αν υπάρχει ρητά ορισμένος προϊστάμενος
        if self.manager:
            return self.manager
        # Αν δεν υπάρχει, ψάχνουμε για χρήστη με ρόλο MANAGER στο τμήμα
        return self.users.filter(roles__code='MANAGER').first()


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
    name_accusative = models.CharField('Ονοματεπώνυμο (Αιτιατική)', max_length=150, blank=True,
        help_text='Αυτόματα δημιουργείται από το Όνομα και Επίθετο, π.χ. "Γεώργιο Νικολόπουλο"')

    def save(self, *args, **kwargs):
        if self.first_name and self.last_name:
            first = convert_first_name_to_accusative(self.first_name)
            last = convert_last_name_to_accusative(self.last_name)
            if self.name_accusative != f"{first} {last}":
                self.name_accusative = f"{first} {last}"
        super().save(*args, **kwargs)

    email = models.EmailField('Email', unique=True)
    phone1 = models.CharField('Τηλέφωνο 1', max_length=15, blank=True)
    GENDER_CHOICES = [
        ('MALE', 'Άνδρας'),
        ('FEMALE', 'Γυναίκα'),
        ('OTHER', 'Άλλο'),
    ]
    gender = models.CharField('Φύλο', max_length=10, choices=GENDER_CHOICES, blank=True)
    father_name = models.CharField('Πατρώνυμο', max_length=50, blank=True)
    
    # Υπηρεσιακά στοιχεία
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='Τμήμα', related_name='users')
    roles = models.ManyToManyField(Role, verbose_name='Ρόλοι', blank=True, related_name='users')
    user_category = models.CharField('Κατηγορία Χρήστη', max_length=20, choices=USER_CATEGORIES,
                                   default='OTHER', blank=True)
    employee_type = models.ForeignKey('EmployeeType', on_delete=models.SET_NULL, null=True, blank=True,
                                     verbose_name='Τύπος Υπαλλήλου', related_name='users')
    specialty = models.ForeignKey(Specialty, on_delete=models.SET_NULL, null=True, blank=True,
                                verbose_name='Ειδικότητα', related_name='users')
    
    # Επιπλέον στοιχεία χρήστη
    notification_recipients = models.TextField('Κοινοποίηση Απόφασης', blank=True,
                                   help_text='Υπηρεσίες που θα γίνει κοινοποίηση η απόφαση της άδειας')
    role_description = models.TextField('Περιγραφή Ρόλου', blank=True,
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
    
    # Δικαιώματα άδειας
    can_request_leave = models.BooleanField('Δικαίωμα Αίτησης Άδειας', default=True,
        help_text='Αν είναι False, ο χρήστης δεν μπορεί να κάνει αίτηση άδειας (π.χ. SDEY managers, Περιφ. Δ/ντής)')
    
    # Κατάσταση Αδειών
    annual_leave_entitlement = models.IntegerField('Δικαιούμενες Ημέρες Κανονικής Άδειας', default=25,
                                                 help_text='Οι ημέρες κανονικής άδειας που δικαιούται κάθε χρόνο')
    carryover_leave_days = models.IntegerField('Υπόλοιπο Κανονικών Αδειών Προηγούμενου Έτους', default=0,
                                             help_text='Μη εξαντλημένες κανονικές άδειες από το προηγούμενο έτος')
    current_year_leave_balance = models.IntegerField('Υπόλοιπο Κανονικών Αδειών Τρέχοντος Έτους', default=0,
                                                   help_text='Διαθέσιμες κανονικές άδειες για το τρέχον έτος')
    leave_balance = models.IntegerField('Υπόλοιπο Κανονικών Αδειών', default=0,
                                       help_text='Συνολικό υπόλοιπο κανονικών αδειών (προηγούμενο + τρέχον έτος)')
    current_regular_leave_balance = models.IntegerField('Τρέχον Υπόλοιπο Κανονικών (Ledger)', default=0,
                                                        help_text='Denormalized cache του τελευταίου balance_after από το ledger')
    sick_leave_with_declaration = models.IntegerField('Αναρρωτικές Άδειες με Υπεύθυνη Δήλωση', default=2,
                                                    help_text='Διαθέσιμες αναρρωτικές άδειες με υπεύθυνη δήλωση')
    sick_days_current_year = models.IntegerField('Αναρρωτικές Τρέχοντος Έτους', default=0,
                                                 help_text='Σύνολο αναρρωτικών ημερών τρέχοντος έτους (για alert Υγειονομικής)')
    total_sick_leave_last_5_years = models.IntegerField('Σύνολο Αναρρωτικών Αδειών Τελευταίας Πενταετίας',
                                                      default=0, blank=True, null=True,
                                                      help_text='Συνολικές αναρρωτικές άδειες των τελευταίων 5 ετών')
    
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
        return self.roles.filter(code='LEAVE_HANDLER').exists()
    
    @property
    def is_administrator(self):
        return self.roles.filter(code='administrator').exists()
    
    @property
    def is_secretary(self):
        return self.roles.filter(code='SECRETARY').exists()
    
    @property
    def is_employee(self):
        return self.roles.filter(code='EMPLOYEE').exists()
    
    @property
    def manager(self):
        """Επιστρέφει τον προϊστάμενο βάσει του τμήματος"""
        if self.department:
            return self.department.get_department_manager()
        return None
    
    def is_manager_of_department(self, department):
        """Ελέγχει αν ο χρήστης είναι manager του συγκεκριμένου τμήματος"""
        if not department:
            return False
        # Ελέγχουμε αν είναι ο ρητά ορισμένος manager του τμήματος
        if department.manager and department.manager.id == self.id:
            return True
        # Ή έχει τον ρόλο MANAGER στο τμήμα
        return self.roles.filter(code='MANAGER').exists() and self.department_id == department.id
    
    def get_approving_manager(self):
        """
        Επιστρέφει ποιος προϊστάμενος θα εγκρίνει την αίτηση άδειας αυτού του χρήστη.
        
        Λογική:
        1. Αν ο χρήστης είναι manager του τμήματός του → εγκρίνει ο γονικού τμήματος ή PDEDE
        2. Αν ο χρήστης ΔΕΝ είναι manager → εγκρίνει ο manager του τμήματός του
        3. Αν δεν υπάρχει manager → ανεβαίνουμε στο γονικό τμήμα ή PDEDE
        """
        if not self.department:
            return None
        
        # Αν είναι manager του τμήματός του, ψάχνουμε τον γονικού ή PDEDE
        if self.is_manager_of_department(self.department):
            if self.department.parent_department:
                # Αναδρομικά βρίσκουμε τον πρώτο manager πάνω στην ιεραρχία
                return self._find_manager_in_hierarchy(self.department.parent_department)
            else:
                # Είναι root τμήμα, ψάχνουμε για PDEDE
                return self._find_pdede_manager()
        
        # Δεν είναι manager, βρίσκουμε τον manager του τμήματός του
        return self._find_manager_in_hierarchy(self.department)
    
    def _find_pdede_manager(self):
        """Βρίσκει τον manager του PDEDE department όταν δεν υπάρχει parent."""
        pdede = Department.objects.filter(
            department_type__code='PDEDE_MAIN'
        ).first()
        if pdede:
            if pdede.manager and pdede.manager != self:
                return pdede.manager
            manager = pdede.users.filter(roles__code='MANAGER').exclude(pk=self.pk).first()
            if manager:
                return manager
        return None
    
    def _find_manager_in_hierarchy(self, department):
        """
        Αναζητά τον πρώτο manager ξεκινώντας από το τμήμα και ανεβαίνοντας στην ιεραρχία.
        Αν δεν βρει parent, ψάχνει για PDEDE department.
        """
        while department:
            # Πρώτα ελέγχουμε αν υπάρχει ρητά ορισμένος manager
            if department.manager and department.manager != self:
                return department.manager
            # Διαφορετικά ψάχνουμε για χρήστη με ρόλο MANAGER
            manager = department.users.filter(roles__code='MANAGER').exclude(pk=self.pk).first()
            if manager:
                return manager
            # Αν δεν βρούμε, πάμε στο γονικό
            department = department.parent_department
        
        # Αν φτάσαμε εδώ χωρίς parent, ψάχνουμε για PDEDE department
        return self._find_pdede_manager()
    
    def has_leave_request_permission(self):
        """Ελέγχει αν ο χρήστης μπορεί να αιτηθεί άδεια"""
        # ΣΔΕΥ χωρίς γονικό ΚΕΔΑΣΥ δεν μπορούν να αιτηθούν
        from accounts.department_utils import is_sdey_department, is_sdey_under_kedasy
        if is_sdey_department(self.department) and not is_sdey_under_kedasy(self.department):
            return False

        # Αν το πεδίο can_request_leave είναι False, δεν μπορεί
        field_value = self._meta.get_field('can_request_leave').value_from_object(self)
        if not field_value:
            return False

        # Αν είναι manager του τμήματός του και δεν έχει γονικό τμήμα, δεν μπορεί
        if self.department and self.is_manager_of_department(self.department):
            if not self.department.parent_department:
                return False
        return True
    
    def can_approve_leaves(self):
        """Μπορεί να εγκρίνει αιτήσεις αδειών"""
        return self.roles.filter(code__in=['MANAGER', 'LEAVE_HANDLER', 'administrator']).exists()
    
    def get_subordinates(self):
        """Επιστρέφει τους υφισταμένους του χρήστη"""
        if self.is_department_manager and self.department:
            from django.db.models import Q
            
            # Χρήστες από το ίδιο τμήμα που δεν είναι προϊστάμενοι
            conditions = Q(
                department=self.department,
                is_active=True
            ) & ~Q(roles__code='MANAGER')
            
            # Αν είναι προϊστάμενος ΚΕΔΑΣΥ, περιλαμβάνουμε και τους υπαλλήλους των ΣΔΕΥ
            if (self.department.department_type and
                self.department.department_type.code == 'KEDASY'):
                # Προσθέτουμε condition για ΣΔΕΥ υπαλλήλους
                from accounts.department_utils import SDEY_DEPARTMENT_TYPE_CODES
                sdei_condition = Q(
                    department__parent_department=self.department,
                    department__department_type__code__in=SDEY_DEPARTMENT_TYPE_CODES,
                    is_active=True
                ) & ~Q(roles__code='MANAGER')
                
                # Ενώνουμε τα conditions με OR
                conditions = conditions | sdei_condition
            
            # Αν είναι προϊστάμενος της Αυτοτελούς Διεύθυνσης, περιλαμβάνουμε χρήστες από τα child departments
            if self.department.code == 'AUTOTELOUS_DN':
                # Προσθέτουμε condition για χρήστες από child departments
                child_dept_condition = Q(
                    department__parent_department=self.department,
                    is_active=True
                )
                
                # Ενώνουμε τα conditions με OR
                conditions = conditions | child_dept_condition
            
            return User.objects.filter(conditions).distinct()
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
        """Εγκρίνει την εγγραφή του χρήστη και στέλνει ειδοποίηση/email"""
        from django.utils import timezone
        self.registration_status = 'APPROVED'
        self.approved_by = approved_by_user
        self.approval_date = timezone.now()
        self.approval_notes = notes
        self.is_active = True  # Ενεργοποίηση του χρήστη
        self.save()
        
        # Αποστολή email ειδοποίησης
        try:
            from pdede_leaves.email_utils import (
                send_registration_approved_email,
                send_registration_approved_notification
            )
            send_registration_approved_email(self)
            send_registration_approved_notification(self)
        except Exception:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not send approval notifications for user {self.email}")
    
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
    
    # Μέθοδοι διαχείρισης κανονικών αδειών
    def calculate_total_leave_balance(self):
        """Υπολογίζει το συνολικό υπόλοιπο κανονικών αδειών"""
        return self.carryover_leave_days + self.current_year_leave_balance
    
    def update_leave_balance(self):
        """Ενημερώνει το πεδίο leave_balance με βάση τα υπόλοιπα"""
        self.leave_balance = self.calculate_total_leave_balance()
        self.save()
    
    def can_request_leave_days(self, requested_days):
        """Ελέγχει αν ο χρήστης μπορεί να αιτηθεί συγκεκριμένο αριθμό ημερών"""
        return self.leave_balance >= requested_days
    
    def use_leave_days(self, days_used):
        """
        Χρησιμοποιεί ημέρες κανονικής άδειας
        Πρώτα εξαντλούνται οι άδειες προηγούμενου έτους, μετά του τρέχοντος
        """
        import logging
        logger = logging.getLogger(__name__)

        if days_used <= 0:
            return False

        if not self.can_request_leave_days(days_used):
            return False

        remaining_days = days_used

        # Πρώτα αφαιρούμε από το υπόλοιπο προηγούμενου έτους
        if self.carryover_leave_days > 0:
            days_from_carryover = min(remaining_days, self.carryover_leave_days)
            self.carryover_leave_days -= days_from_carryover
            remaining_days -= days_from_carryover

        # Μετά αφαιρούμε από το τρέχον έτος
        if remaining_days > 0:
            self.current_year_leave_balance -= remaining_days

        # Ενημερώνουμε το συνολικό υπόλοιπο
        self.leave_balance = self.calculate_total_leave_balance()
        self.save()

        logger.info(f"Used {days_used} leave days for user {self.email}")

        return True
    
    def reset_yearly_leave_balance(self):
        """
        Μηδενίζει τα υπόλοιπα στην αρχή του έτους
        Μεταφέρει το τρέχον υπόλοιπο στο προηγούμενο έτος
        """
        # Μεταφορά υπολοίπου τρέχοντος έτους στο προηγούμενο
        self.carryover_leave_days = self.current_year_leave_balance
        
        # Νέες άδειες για το τρέχον έτος
        self.current_year_leave_balance = self.annual_leave_entitlement
        
        # Ενημέρωση συνολικού υπολοίπου
        self.leave_balance = self.calculate_total_leave_balance()
        self.save()
    
    def get_leave_balance_breakdown(self):
        """Επιστρέφει αναλυτικά τα υπόλοιπα αδειών"""
        return {
            'carryover_days': self.carryover_leave_days,
            'current_year_days': self.current_year_leave_balance,
            'total_days': self.calculate_total_leave_balance(),
            'annual_entitlement': self.annual_leave_entitlement
        }


class EmployeeType(models.Model):
    """Τύποι υπαλλήλων (αντικαθιστά το hardcoded USER_CATEGORIES)"""
    name = models.CharField('Όνομα Τύπου', max_length=100, unique=True)
    description = models.TextField('Περιγραφή', blank=True)
    is_active = models.BooleanField('Ενεργός', default=True)
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)

    class Meta:
        verbose_name = 'Τύπος Υπαλλήλου'
        verbose_name_plural = 'Τύποι Υπαλλήλων'
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def create_defaults(cls):
        """Δημιουργεί τους default τύπους αν δεν υπάρχουν"""
        defaults = [
            {'name': 'Διοικητικοί', 'description': 'Μόνιμο διοικητικό προσωπικό'},
            {'name': 'Εκπαιδευτικοί', 'description': 'Μόνιμο εκπαιδευτικό προσωπικό'},
            {'name': 'Αναπληρωτές', 'description': 'Αναπληρωτές εκπαιδευτικοί'},
            {'name': 'Κέντρο Στήριξης ΣΔΕΥ', 'description': 'Υπεύθυνοι Κέντρου Στήριξης ΣΔΕΥ'},
            {'name': 'Δ/ντες Εκπαίδευσης', 'description': 'Περιφερειακός Διευθυντής'},
            {'name': 'Άλλο', 'description': 'Άλλες κατηγορίες'},
        ]
        for d in defaults:
            cls.objects.get_or_create(name=d['name'], defaults={'description': d['description']})
