from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import LeaveRequest, LeaveType
from .widgets import GreekDateInput
from datetime import datetime


class LeaveRequestForm(forms.ModelForm):
    """Φόρμα αίτησης άδειας"""
    
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'start_date', 'end_date', 'description']
        widgets = {
            'start_date': GreekDateInput(),
            'end_date': GreekDateInput(),
            'leave_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Προαιρετική περιγραφή ή αιτιολογία για την άδεια...'
            }),
        }
        labels = {
            'leave_type': 'Τύπος Άδειας',
            'start_date': 'Ημερομηνία Έναρξης',
            'end_date': 'Ημερομηνία Λήξης',
            'description': 'Περιγραφή/Αιτιολογία',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Μόνο ενεργοί τύποι αδειών
        self.fields['leave_type'].queryset = LeaveType.objects.filter(is_active=True)
        
        # Προσθήκη help_text
        self.fields['start_date'].help_text = 'Μορφή: ηη/μμ/εεεε'
        self.fields['end_date'].help_text = 'Μορφή: ηη/μμ/εεεε'
    
    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if start_date and start_date < timezone.now().date():
            raise ValidationError('Η ημερομηνία έναρξης δεν μπορεί να είναι στο παρελθόν.')
        return start_date
    
    def clean_end_date(self):
        end_date = self.cleaned_data.get('end_date')
        if end_date and end_date < timezone.now().date():
            raise ValidationError('Η ημερομηνία λήξης δεν μπορεί να είναι στο παρελθόν.')
        return end_date
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError('Η ημερομηνία έναρξης δεν μπορεί να είναι μεταγενέστερη της ημερομηνίας λήξης.')
            
            # Υπολογισμός ημερών
            total_days = (end_date - start_date).days + 1
            if total_days > 365:
                raise ValidationError('Η άδεια δεν μπορεί να υπερβαίνει τις 365 ημέρες.')
        
        return cleaned_data


class ApproveRejectForm(forms.Form):
    """Φόρμα έγκρισης/απόρριψης αίτησης"""
    
    ACTION_CHOICES = [
        ('approve', 'Έγκριση'),
        ('reject', 'Απόρριψη'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect,
        label='Ενέργεια'
    )
    
    comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Προαιρετικά σχόλια...'
        }),
        label='Σχόλια'
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        comments = cleaned_data.get('comments')
        
        if action == 'reject' and not comments:
            raise ValidationError('Τα σχόλια είναι υποχρεωτικά για την απόρριψη.')
        
        return cleaned_data


class ProcessLeaveForm(forms.Form):
    """Φόρμα επεξεργασίας αίτησης από χειριστή"""
    
    protocol_number = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'π.χ. ΠΔΕΔΕ/12345/2024'
        }),
        label='Αριθμός Πρωτοκόλλου'
    )
    
    comments = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Σχόλια επεξεργασίας...'
        }),
        label='Σχόλια Επεξεργασίας'
    )


class RejectLeaveForm(forms.Form):
    """Φόρμα απόρριψης αίτησης"""
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Αναφέρετε την αιτιολογία απόρριψης...'
        }),
        label='Αιτιολογία Απόρριψης'
    )