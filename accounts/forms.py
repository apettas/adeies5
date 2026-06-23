from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import User, Department, Specialty, normalize_person_name_lower


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
        help_text='Από το Σχολικό Δίκτυο, σε πεζά γράμματα. Ελέγξτε και διορθώστε αν χρειάζεται.',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. γεώργιος'
        })
    )
    
    last_name = forms.CharField(
        max_length=50,
        required=True,
        label='Επώνυμο',
        help_text='Από το Σχολικό Δίκτυο, σε πεζά γράμματα. Ελέγξτε και διορθώστε αν χρειάζεται.',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. νικολάου'
        })
    )
    
    father_name = forms.CharField(
        max_length=50,
        required=False,
        label='Πατρώνυμο',
        help_text='Από το Σχολικό Δίκτυο (gsnfathername), σε πεζά. Ελέγξτε και διορθώστε αν χρειάζεται.',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. ιωάννης'
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
        help_text='Από το Σχολικό Δίκτυο (employeeNumber). Μπορείτε να το διορθώσετε.',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. 12345'
        })
    )

    gsn_branch = forms.CharField(
        max_length=100,
        required=False,
        label='Κλάδος',
        help_text='Από το Σχολικό Δίκτυο (gsnBranch). Μπορείτε να το διορθώσετε.',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. ΠΕ02'
        })
    )

    sso_organizational_unit = forms.CharField(
        max_length=255,
        required=False,
        label='Οργανική Μονάδα (ou)',
        help_text='Από το Σχολικό Δίκτυο — σχολική/υπηρεσιακή μονάδα.',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. 1ο Λύκειο Νέου Ψυχικού'
        })
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
    
    role_description = forms.CharField(
        max_length=200,
        required=False,
        label='Υπηρεσιακή Ιδιότητα',
        help_text='Από το Σχολικό Δίκτυο (title). Π.χ. Αναπληρωτής Εκπαιδευτικός.',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Περιγράψτε την υπηρεσιακή σας ιδιότητα'
        })
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
    
    def clean_first_name(self):
        value = self.cleaned_data.get('first_name', '')
        if not value.strip():
            raise ValidationError('Το όνομα είναι υποχρεωτικό')
        return normalize_person_name_lower(value)
    
    def clean_last_name(self):
        value = self.cleaned_data.get('last_name', '')
        if not value.strip():
            raise ValidationError('Το επώνυμο είναι υποχρεωτικό')
        return normalize_person_name_lower(value)

    def clean_father_name(self):
        value = self.cleaned_data.get('father_name', '')
        if not value:
            return ''
        return normalize_person_name_lower(value)

    def clean_name_accusative(self):
        value = self.cleaned_data.get('name_accusative', '')
        if not value.strip():
            raise ValidationError('Το ονοματεπώνυμο στην αιτιατική είναι υποχρεωτικό')
        return value.strip()
    
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
