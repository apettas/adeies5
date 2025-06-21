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


class User(AbstractUser):
    """Επεκτεταμένο μοντέλο χρήστη"""
    
    USER_ROLES = [
        ('employee', 'Υπάλληλος'),
        ('department_manager', 'Προϊστάμενος Τμήματος'),
        ('leave_handler', 'Χειριστής Αδειών'),
        ('administrator', 'Διαχειριστής'),
    ]
    
    # Προσωπικά στοιχεία
    first_name = models.CharField('Όνομα', max_length=50)
    last_name = models.CharField('Επίθετο', max_length=50)
    email = models.EmailField('Email', unique=True)
    phone = models.CharField('Τηλέφωνο', max_length=15, blank=True)
    
    # Υπηρεσιακά στοιχεία
    employee_id = models.CharField('Αριθμός Μητρώου', max_length=20, unique=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name='Τμήμα')
    role = models.CharField('Ρόλος', max_length=20, choices=USER_ROLES, default='employee')
    manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                              verbose_name='Προϊστάμενος')
    
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
    
    def is_department_manager(self):
        return self.role == 'department_manager'
    
    def is_leave_handler(self):
        return self.role == 'leave_handler'
    
    def is_administrator(self):
        return self.role == 'administrator'
    
    def can_approve_leaves(self):
        """Μπορεί να εγκρίνει αιτήσεις αδειών"""
        return self.role in ['department_manager', 'leave_handler', 'administrator']
    
    def get_subordinates(self):
        """Επιστρέφει τους υφισταμένους του χρήστη"""
        if self.is_department_manager():
            return User.objects.filter(manager=self, is_active=True)
        return User.objects.none()