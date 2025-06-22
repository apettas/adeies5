from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import User, Department, Specialty


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
        label='Email (Θεσμικό)',
        help_text='Χρησιμοποιήστε το θεσμικό σας email που καταλήγει σε @sch.gr',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@sch.gr'
        })
    )
    
    employee_id = forms.CharField(
        max_length=20,
        required=False,
        label='Αριθμός Μητρώου',
        help_text='Προαιρετικό - Μπορείτε να το συμπληρώσετε αργότερα',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. 12345'
        })
    )
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        required=True,
        label='Τμήμα',
        empty_label='Επιλέξτε Τμήμα',
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
        fields = ('email', 'first_name', 'last_name', 'employee_id',
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
                    'Το email πρέπει να είναι θεσμικό και να καταλήγει σε @sch.gr'
                )
            
            # Έλεγχος αν το email υπάρχει ήδη
            if User.objects.filter(email=email).exists():
                raise ValidationError(
                    'Αυτό το email χρησιμοποιείται ήδη από άλλον χρήστη'
                )
        return email

    def clean_employee_id(self):
        employee_id = self.cleaned_data.get('employee_id')
        if employee_id:
            # Έλεγχος αν ο αριθμός μητρώου υπάρχει ήδη
            if User.objects.filter(employee_id=employee_id).exists():
                raise ValidationError(
                    'Αυτός ο αριθμός μητρώου χρησιμοποιείται ήδη'
                )
        return employee_id

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.employee_id = self.cleaned_data.get('employee_id', '')
        user.department = self.cleaned_data['department']
        user.specialty = self.cleaned_data['specialty']
        user.phone = self.cleaned_data.get('phone', '')
        user.address = self.cleaned_data.get('address', '')
        
        # Κρίσιμο: Proper password hashing
        user.set_password(self.cleaned_data['password1'])
        
        if commit:
            user.save()
        return user