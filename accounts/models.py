from django.contrib.auth.models import AbstractUser
from django.db import models


class Department(models.Model):
    """Μοντέλο για τα Τμήματα/Γραφεία της ΠΔΕΔΕ"""
    
    DEPARTMENT_TYPES = [
        ('DIRECTION', 'Διεύθυνση'),
        ('AUTONOMOUS_DIRECTION', 'Αυτοτελής Διεύθυνση'),
        ('DEPARTMENT', 'Τμήμα'),
        ('OFFICE', 'Γραφείο'),
    ]
    
    name = models.CharField('Όνομα Τμήματος', max_length=200)
    code = models.CharField('Κωδικός Τμήματος', max_length=10, unique=True)
    department_type = models.CharField('Τύπος Τμήματος', max_length=30, choices=DEPARTMENT_TYPES)
    parent_department = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, 
                                        verbose_name='Γονικό Τμήμα')
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


class User(AbstractUser):
    """Επεκτεταμένο μοντέλο χρήστη"""
    
    # Προσωπικά στοιχεία
    first_name = models.CharField('Όνομα', max_length=50)
    last_name = models.CharField('Επίθετο', max_length=50)
    email = models.EmailField('Email', unique=True)
    phone = models.CharField('Τηλέφωνο', max_length=15, blank=True)
    
    # Υπηρεσιακά στοιχεία
    employee_id = models.CharField('Αριθμός Μητρώου', max_length=20, unique=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='Τμήμα', related_name='users')
    roles = models.ManyToManyField(Role, verbose_name='Ρόλοι', blank=True, related_name='users')
    
    # Ημερομηνίες
    hire_date = models.DateField('Ημερομηνία Πρόσληψης', null=True, blank=True)
    is_active = models.BooleanField('Ενεργός', default=True)
    
    # Django fields
    username = models.CharField('Όνομα Χρήστη', max_length=150, unique=True)
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email', 'first_name', 'last_name']
    
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
        return self.roles.filter(code='department_manager').exists()
    
    @property
    def is_leave_handler(self):
        return self.roles.filter(code='leave_handler').exists()
    
    @property
    def is_administrator(self):
        return self.roles.filter(code='administrator').exists()
    
    @property
    def is_employee(self):
        return self.roles.filter(code='employee').exists()
    
    @property
    def manager(self):
        """Επιστρέφει τον προϊστάμενο βάσει του τμήματος"""
        if self.department:
            return self.department.get_department_manager()
        return None
    
    def can_approve_leaves(self):
        """Μπορεί να εγκρίνει αιτήσεις αδειών"""
        return self.roles.filter(code__in=['department_manager', 'leave_handler', 'administrator']).exists()
    
    def get_subordinates(self):
        """Επιστρέφει τους υφισταμένους του χρήστη"""
        if self.is_department_manager and self.department:
            # Χρήστες από το ίδιο τμήμα που δεν είναι προϊστάμενοι
            return User.objects.filter(
                department=self.department,
                is_active=True
            ).exclude(roles__code='department_manager')
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