from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from accounts.role_constants import ROLE_EMPLOYEE
from .models import (
    User,
    Department,
    Specialty,
    Role,
    EmployeeType,
    normalize_person_name_lower,
    validate_greek_name_characters,
    GREEK_NAME_HELP_TEXT,
)


class UserRegistrationForm(UserCreationForm):
    """Form για εγγραφή νέων χρηστών"""
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        label='Όνομα',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Εισάγετε το όνομά σας'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        label='Επώνυμο',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Εισάγετε το επώνυμό σας'
        })
    )
    
    email = forms.EmailField(
        required=True,
        label='Email (προσωπικό Υπηρεσιακό)',
        help_text='Χρησιμοποιήστε το προσωπικό υπηρεσιακό σας email που καταλήγει σε @sch.gr',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@sch.gr'
        })
    )
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=True,
        label='Υπηρεσία Υπηρέτησης',
        empty_label='Επιλέξτε Υπηρεσία Υπηρέτησης',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    specialty = forms.ModelChoiceField(
        queryset=Specialty.objects.filter(is_active=True),
        required=True,
        label='Ειδικότητα',
        empty_label='Επιλέξτε Ειδικότητα',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    phone = forms.CharField(
        max_length=15,
        required=False,
        label='Τηλέφωνο',
        help_text='Προαιρετικό',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. 2610123456'
        })
    )
    
    address = forms.CharField(
        max_length=200,
        required=False,
        label='Διεύθυνση',
        help_text='Προαιρετικό',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Διεύθυνση'
        })
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        label='Αποδέχομαι τους όρους χρήσης',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name',
                 'department', 'specialty', 'phone', 'address',
                 'password1', 'password2', 'terms_accepted')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Προσαρμογή των default password fields
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Εισάγετε κωδικό πρόσβασης'
        })
        self.fields['password1'].label = 'Κωδικός Πρόσβασης'
        
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Επιβεβαίωση κωδικού'
        })
        self.fields['password2'].label = 'Επιβεβαίωση Κωδικού'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Έλεγχος αν το email καταλήγει σε @sch.gr
            if not email.endswith('@sch.gr'):
                raise ValidationError(
                    'Το email πρέπει να είναι προσωπικό υπηρεσιακό και να καταλήγει σε @sch.gr'
                )
            
            # Έλεγχος αν το email υπάρχει ήδη
            if User.objects.filter(email=email).exists():
                raise ValidationError(
                    'Αυτό το email χρησιμοποιείται ήδη από άλλον χρήστη'
                )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.department = self.cleaned_data['department']
        user.specialty = self.cleaned_data['specialty']
        user.phone1 = self.cleaned_data.get('phone', '')
        
        # Κρίσιμο: Proper password hashing
        user.set_password(self.cleaned_data['password1'])
        
        if commit:
            user.save()
        return user


class HandlerUserActivationForm(forms.ModelForm):
    """Φόρμα χειριστή για συμπλήρωση πεδίων και ενεργοποίηση εκκρεμούς εγγραφής."""

    approval_notes = forms.CharField(
        required=False,
        label='Σημειώσεις Έγκρισης',
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
    )

    class Meta:
        model = User
        fields = (
            'first_name',
            'last_name',
            'name_accusative',
            'father_name',
            'gender',
            'phone1',
            'employee_number',
            'gsn_branch',
            'sso_organizational_unit',
            'role_description',
            'department',
            'specialty',
            'employee_type',
            'roles',
            'notification_recipients',
            'annual_leave_entitlement',
            'current_regular_leave_balance',
            'can_request_leave',
        )
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'name_accusative': forms.TextInput(attrs={'class': 'form-control'}),
            'father_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'phone1': forms.TextInput(attrs={'class': 'form-control'}),
            'employee_number': forms.TextInput(attrs={'class': 'form-control'}),
            'gsn_branch': forms.TextInput(attrs={'class': 'form-control'}),
            'sso_organizational_unit': forms.TextInput(attrs={'class': 'form-control'}),
            'role_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'specialty': forms.Select(attrs={'class': 'form-select'}),
            'employee_type': forms.Select(attrs={'class': 'form-select'}),
            'roles': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 6}),
            'notification_recipients': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'annual_leave_entitlement': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'current_regular_leave_balance': forms.NumberInput(attrs={'class': 'form-control'}),
            'can_request_leave': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['phone1'].label = 'Τηλέφωνο'
        self.fields['department'].queryset = Department.objects.filter(is_active=True).order_by('name')
        self.fields['specialty'].queryset = Specialty.objects.filter(is_active=True).order_by(
            'specialties_short', 'specialties_full',
        )
        self.fields['employee_type'].queryset = EmployeeType.objects.filter(is_active=True).order_by('name')
        self.fields['roles'].queryset = Role.objects.filter(is_active=True).order_by('name')
        self.fields['employee_type'].required = True
        self.fields['department'].required = True
        self.fields['specialty'].required = True
        self.fields['first_name'].required = True
        self.fields['last_name'].required = True

        if self.instance and self.instance.pk:
            if not self.is_bound and not self.instance.roles.exists():
                employee_role = Role.objects.filter(code=ROLE_EMPLOYEE, is_active=True).first()
                if employee_role:
                    self.initial.setdefault('roles', [employee_role.pk])
            if self.instance.current_regular_leave_balance == 0:
                self.fields['current_regular_leave_balance'].initial = (
                    self.instance.annual_leave_entitlement or 25
                )


class CompleteSSORegistrationForm(forms.Form):
    """Form για συμπλήρωση στοιχείων από νέο CAS (SSO) χρήστη"""
    
    email = forms.EmailField(
        required=True,
        label='Email ΠΣΔ',
        widget=forms.HiddenInput(),
    )
    
    first_name = forms.CharField(
        max_length=50,
        required=True,
        label='Όνομα',
        help_text=GREEK_NAME_HELP_TEXT,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. Γεώργιος'
        })
    )
    
    last_name = forms.CharField(
        max_length=50,
        required=True,
        label='Επώνυμο',
        help_text=GREEK_NAME_HELP_TEXT,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. Νικολάου'
        })
    )
    
    father_name = forms.CharField(
        max_length=50,
        required=False,
        label='Πατρώνυμο',
        help_text=GREEK_NAME_HELP_TEXT,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. Ιωάννης'
        })
    )

    name_accusative = forms.CharField(
        max_length=150,
        required=True,
        label='Ονοματεπώνυμο (Αιτιατική)',
        help_text='Καταχωρήστε το ονοματεπώνυμό σας στην αιτιατική, π.χ. «γεώργιο νικολάου».',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. γεώργιο νικολάου'
        })
    )

    employee_number = forms.CharField(
        max_length=30,
        required=False,
        label='Αριθμός Μητρώου',
        widget=forms.HiddenInput(),
    )

    gsn_branch = forms.CharField(
        max_length=100,
        required=False,
        label='Κλάδος (Ειδικότητα)',
        widget=forms.HiddenInput(),
    )

    sso_organizational_unit = forms.CharField(
        max_length=255,
        required=False,
        label='Οργανική Μονάδα (ou)',
        widget=forms.HiddenInput(),
    )
    
    gender = forms.ChoiceField(
        choices=[('', 'Επιλέξτε Φύλο'), ('MALE', 'Άνδρας'), ('FEMALE', 'Γυναίκα'), ('OTHER', 'Άλλο')],
        required=False,
        label='Φύλο',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=True,
        label='Υπηρεσία-Τμήμα τρέχουσας υπηρέτησης',
        empty_label='Επιλέξτε Υπηρεσία-Τμήμα',
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    phone = forms.CharField(
        max_length=15,
        required=False,
        label='Τηλέφωνο',
        help_text='Προαιρετικό',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. 2610123456'
        })
    )
    
    role_description = forms.CharField(
        max_length=200,
        required=False,
        label='Υπηρεσιακή Ιδιότητα',
        widget=forms.HiddenInput(),
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        label='Αποδέχομαι τους όρους χρήσης',
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.target_email = kwargs.pop('target_email', None)
        super().__init__(*args, **kwargs)
        if self.target_email:
            self.fields['email'].initial = self.target_email

    def clean_email(self):
        if self.target_email:
            return self.target_email
        return self.cleaned_data.get('email')

    def clean_employee_number(self):
        """Αριθμός μητρώου από ΠΣΔ — δεν επιτρέπεται τροποποίηση από τον χρήστη."""
        if self.target_email:
            try:
                user = User.objects.get(email=self.target_email)
                return user.employee_number
            except User.DoesNotExist:
                pass
        return self.cleaned_data.get('employee_number') or None

    def _clean_psd_readonly_field(self, field_name):
        if self.target_email:
            try:
                user = User.objects.get(email=self.target_email)
                return getattr(user, field_name) or ''
            except User.DoesNotExist:
                pass
        return self.cleaned_data.get(field_name) or ''

    def clean_gsn_branch(self):
        return self._clean_psd_readonly_field('gsn_branch')

    def clean_sso_organizational_unit(self):
        return self._clean_psd_readonly_field('sso_organizational_unit')

    def clean_role_description(self):
        return self._clean_psd_readonly_field('role_description')
    
    def clean_first_name(self):
        value = self.cleaned_data.get('first_name', '')
        if not value.strip():
            raise ValidationError('Το όνομα είναι υποχρεωτικό')
        value = value.strip()
        validate_greek_name_characters(value, 'Όνομα')
        return normalize_person_name_lower(value)
    
    def clean_last_name(self):
        value = self.cleaned_data.get('last_name', '')
        if not value.strip():
            raise ValidationError('Το επώνυμο είναι υποχρεωτικό')
        value = value.strip()
        validate_greek_name_characters(value, 'Επώνυμο')
        return normalize_person_name_lower(value)

    def clean_father_name(self):
        value = self.cleaned_data.get('father_name', '')
        if not value:
            return ''
        value = value.strip()
        validate_greek_name_characters(value, 'Πατρώνυμο')
        return normalize_person_name_lower(value)

    def clean_name_accusative(self):
        value = self.cleaned_data.get('name_accusative', '')
        if not value.strip():
            raise ValidationError('Το ονοματεπώνυμο στην αιτιατική είναι υποχρεωτικό')
        value = normalize_person_name_lower(value)
        validate_greek_name_characters(value, 'Ονοματεπώνυμο (Αιτιατική)')
        return value
    
    def clean(self):
        cleaned_data = super().clean()
        # Verify the user still exists in pending state
        if self.target_email:
            try:
                user = User.objects.get(email=self.target_email)
                if user.registration_status != 'PENDING' and user.registration_status != '':
                    raise ValidationError(
                        'Η εγγραφή σας έχει ήδη ολοκληρωθεί. '
                        'Παρακαλώ συνδεθείτε στο σύστημα.'
                    )
            except User.DoesNotExist:
                raise ValidationError(
                    'Ο λογαριασμός σας δεν βρέθηκε. '
                    'Παρακαλώ κάντε σύνδεση μέσω ΠΣΔ πρώτα.'
                )
        return cleaned_data
