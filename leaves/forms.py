from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import LeaveRequest, LeaveType, LeavePeriod, SecureFile
from .widgets import GreekDateInput
from .crypto_utils import SecureFileHandler
from datetime import datetime
import json


class LeavePeriodForm(forms.ModelForm):
    """Φόρμα για ένα διάστημα άδειας"""
    
    class Meta:
        model = LeavePeriod
        fields = ['start_date', 'end_date']
        widgets = {
            'start_date': GreekDateInput(attrs={
                'class': 'form-control period-start-date',
                'required': True
            }),
            'end_date': GreekDateInput(attrs={
                'class': 'form-control period-end-date',
                'required': True
            }),
        }
        labels = {
            'start_date': 'Ημερομηνία Έναρξης',
            'end_date': 'Ημερομηνία Λήξης',
        }
    
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
        
        return cleaned_data


class LeaveRequestForm(forms.ModelForm):
    """Φόρμα αίτησης άδειας με πολλαπλά διαστήματα"""
    
    # Πεδίο για επισύναψη αρχείου
    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.jpg,.jpeg,.png'
        }),
        label='Επισυνάπτομενο Αρχείο',
        help_text='Επιτρεπτοί τύποι: PDF, JPG, PNG. Μέγιστο μέγεθος: 10MB'
    )
    
    # Κρυφό πεδίο για τα διαστήματα (JSON)
    periods_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'description']
        widgets = {
            'leave_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Προαιρετική περιγραφή ή αιτιολογία για την άδεια...'
            }),
        }
        labels = {
            'leave_type': 'Τύπος Άδειας',
            'description': 'Περιγραφή/Αιτιολογία',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Μόνο ενεργοί τύποι αδειών
        self.fields['leave_type'].queryset = LeaveType.objects.filter(is_active=True)
    
    def clean_periods_data(self):
        """Επικύρωση των διαστημάτων άδειας"""
        periods_json = self.cleaned_data.get('periods_data', '[]')
        
        try:
            periods = json.loads(periods_json)
        except json.JSONDecodeError:
            raise ValidationError('Μη έγκυρα δεδομένα διαστημάτων.')
        
        if not periods:
            raise ValidationError('Πρέπει να προσθέσετε τουλάχιστον ένα διάστημα άδειας.')
        
        validated_periods = []
        total_days = 0
        
        for i, period in enumerate(periods, 1):
            if 'start_date' not in period or 'end_date' not in period:
                raise ValidationError(f'Διάστημα {i}: Λείπουν απαιτούμενα πεδία.')
            
            try:
                start_date = timezone.datetime.strptime(period['start_date'], '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(period['end_date'], '%Y-%m-%d').date()
            except ValueError:
                raise ValidationError(f'Διάστημα {i}: Μη έγκυρη μορφή ημερομηνίας.')
            
            # Επικύρωση ημερομηνιών
            if start_date < timezone.now().date():
                raise ValidationError(f'Διάστημα {i}: Η ημερομηνία έναρξης δεν μπορεί να είναι στο παρελθόν.')
            
            if end_date < timezone.now().date():
                raise ValidationError(f'Διάστημα {i}: Η ημερομηνία λήξης δεν μπορεί να είναι στο παρελθόν.')
            
            if start_date > end_date:
                raise ValidationError(f'Διάστημα {i}: Η ημερομηνία έναρξης δεν μπορεί να είναι μεταγενέστερη της λήξης.')
            
            period_days = (end_date - start_date).days + 1
            total_days += period_days
            
            validated_periods.append({
                'start_date': start_date,
                'end_date': end_date,
                'days': period_days
            })
        
        # Έλεγχος για επικαλύψεις
        for i, period1 in enumerate(validated_periods):
            for j, period2 in enumerate(validated_periods[i+1:], i+1):
                if (period1['start_date'] <= period2['end_date'] and 
                    period1['end_date'] >= period2['start_date']):
                    raise ValidationError(f'Τα διαστήματα {i+1} και {j+1} επικαλύπτονται.')
        
        # Έλεγχος συνολικών ημερών
        if total_days > 365:
            raise ValidationError(f'Οι συνολικές ημέρες άδειας ({total_days}) δεν μπορούν να υπερβαίνουν τις 365.')
        
        return validated_periods
    
    def clean_attachment(self):
        """Επικύρωση αρχείου"""
        file_obj = self.cleaned_data.get('attachment')
        
        if not file_obj:
            return None
        
        # Επικύρωση αρχείου
        is_valid, error_message = SecureFileHandler.validate_file(file_obj)
        
        if not is_valid:
            raise ValidationError(f'Αρχείο "{file_obj.name}": {error_message}')
        
        return file_obj
    
    def save(self, commit=True):
        """Αποθήκευση αίτησης με διαστήματα"""
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            
            # Διαγραφή υπαρχόντων διαστημάτων
            instance.periods.all().delete()
            
            # Δημιουργία νέων διαστημάτων
            validated_periods = self.cleaned_data.get('periods_data', [])
            for period_data in validated_periods:
                LeavePeriod.objects.create(
                    leave_request=instance,
                    start_date=period_data['start_date'],
                    end_date=period_data['end_date']
                )
        
        return instance


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