from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import LeaveRequest, LeaveType, LeavePeriod, SecureFile
from .utils.leave_type_ordering import get_ordered_active_leave_types
from .widgets import GreekDateInput
from .crypto_utils import SecureFileHandler
from datetime import datetime, timedelta
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
            'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png'
        }),
        label='Επισυνάπτομενο Αρχείο',
        help_text='Επιτρεπτοί τύποι: PDF, DOC, DOCX, JPG, PNG. Μέγιστο μέγεθος: 10MB'
    )
    
    # Κρυφό πεδίο για τα διαστήματα (JSON)
    periods_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )

    # Πεδίο ημερών άδειας
    days = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 1,
            'required': True,
        }),
        label='Ημέρες Άδειας',
        help_text='Συμπληρώστε τον συνολικό αριθμό ημερών άδειας'
    )

    class Meta:
        model = LeaveRequest
        fields = ['leave_type', 'description', 'days']
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
        # Οι άτυπες (is_simple) και οι τύποι ανάκλησης δεν εμφανίζονται στο κανονικό create
        self.fields['leave_type'].queryset = get_ordered_active_leave_types(
            LeaveType.objects.filter(is_active=True, is_simple=False, is_revocation=False)
        )
    
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

        # Έλεγχος ότι τα διαστήματα συμφωνούν με τις δηλωμένες ημέρες
        # (το days καθαρίζεται μετά το periods_data — διάβασμα και από raw data)
        declared_days = self.cleaned_data.get('days')
        if declared_days is None and self.data is not None:
            raw_days = self.data.get('days')
            if raw_days not in (None, ''):
                try:
                    declared_days = int(raw_days)
                except (TypeError, ValueError):
                    declared_days = None
        if declared_days is not None and total_days != declared_days:
            raise ValidationError(
                f'Οι συνολικές ημέρες των διαστημάτων ({total_days}) δεν συμφωνούν με τις '
                f'δηλωμένες ημέρες άδειας ({declared_days}). Παρακαλώ διορθώστε.'
            )

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
        days = self.cleaned_data.get('days', 1)
        instance.days = days
        instance.requested_days = days

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


class AtypicalLeaveForm(LeaveRequestForm):
    """Φόρμα για άτυπες άδειες — μόνο is_simple=True types"""

    class Meta(LeaveRequestForm.Meta):
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['leave_type'].queryset = get_ordered_active_leave_types(
            LeaveType.objects.filter(is_simple=True, is_active=True)
        )


class LeaveRevocationForm(forms.Form):
    """Φόρμα ανάκλησης ολοκληρωμένης άδειας (ολική / μερική)."""

    SCOPE_CHOICES = LeaveRequest.REVOCATION_SCOPE_CHOICES

    revocation_scope = forms.ChoiceField(
        choices=SCOPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_revocation_scope'}),
        label='Είδος Ανάκλησης',
        help_text=(
            'Ολική: ανακαλείται ολόκληρη η αρχική άδεια (διαστήματα κλειδωμένα). '
            'Μερική: δηλώστε υποσύνολο διαστημάτων εντός της αρχικής.'
        ),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Προαιρετική αιτιολογία ανάκλησης...',
        }),
        label='Περιγραφή/Αιτιολογία',
    )
    days = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 1,
            'required': True,
        }),
        label='Ημέρες Ανάκλησης',
    )
    periods_data = forms.CharField(widget=forms.HiddenInput(), required=False)
    attachment = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.pdf,.doc,.docx,.jpg,.jpeg,.png',
        }),
        label='Επισυνάπτομενο Αρχείο',
    )

    def __init__(self, *args, parent_leave=None, **kwargs):
        self.parent_leave = parent_leave
        super().__init__(*args, **kwargs)
        remaining = parent_leave.remaining_revocable_days if parent_leave else 0
        if remaining and parent_leave and parent_leave.revoked_days:
            # Μετά από μερική, μόνο μερική ανάκληση του υπολοίπου
            self.fields['revocation_scope'].choices = [('PARTIAL', 'Μερική')]
            self.fields['revocation_scope'].initial = 'PARTIAL'
            self.fields['revocation_scope'].help_text = (
                f'Έχουν ήδη ανακληθεί {parent_leave.revoked_days} ημέρες. '
                f'Μπορείτε να ανακαλέσετε έως {remaining} ακόμη.'
            )

    def clean_periods_data(self):
        periods_json = self.cleaned_data.get('periods_data', '[]')
        try:
            periods = json.loads(periods_json or '[]')
        except json.JSONDecodeError:
            raise ValidationError('Μη έγκυρα δεδομένα διαστημάτων.')

        if not periods:
            raise ValidationError('Πρέπει να προσθέσετε τουλάχιστον ένα διάστημα ανάκλησης.')

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
            if start_date > end_date:
                raise ValidationError(
                    f'Διάστημα {i}: Η ημερομηνία έναρξης δεν μπορεί να είναι μεταγενέστερη της λήξης.'
                )
            period_days = (end_date - start_date).days + 1
            total_days += period_days
            validated_periods.append({
                'start_date': start_date,
                'end_date': end_date,
                'days': period_days,
            })

        for i, period1 in enumerate(validated_periods):
            for j, period2 in enumerate(validated_periods[i + 1:], i + 1):
                if (
                    period1['start_date'] <= period2['end_date']
                    and period1['end_date'] >= period2['start_date']
                ):
                    raise ValidationError(f'Τα διαστήματα {i + 1} και {j + 1} επικαλύπτονται.')

        declared_days = self.cleaned_data.get('days')
        if declared_days is None and self.data is not None:
            raw_days = self.data.get('days')
            if raw_days not in (None, ''):
                try:
                    declared_days = int(raw_days)
                except (TypeError, ValueError):
                    declared_days = None
        if declared_days is not None and total_days != declared_days:
            raise ValidationError(
                f'Οι συνολικές ημέρες των διαστημάτων ({total_days}) δεν συμφωνούν με τις '
                f'δηλωμένες ημέρες ({declared_days}).'
            )

        return validated_periods

    def clean(self):
        cleaned = super().clean()
        parent = self.parent_leave
        if not parent:
            raise ValidationError('Λείπει η αρχική άδεια προς ανάκληση.')

        scope = cleaned.get('revocation_scope')
        periods = cleaned.get('periods_data') or []
        days = cleaned.get('days') or 0
        remaining = parent.remaining_revocable_days

        if days > remaining:
            raise ValidationError(
                f'Δεν μπορείτε να ανακαλέσετε περισσότερες από {remaining} ημέρες '
                f'(υπόλοιπο προς ανάκληση).'
            )

        if scope == 'TOTAL':
            if parent.revoked_days:
                raise ValidationError(
                    'Η ολική ανάκληση επιτρέπεται μόνο όταν δεν έχει γίνει ήδη μερική.'
                )
            if days != parent.total_days:
                raise ValidationError(
                    f'Για ολική ανάκληση πρέπει να δηλωθούν όλες οι ημέρες της αρχικής '
                    f'άδειας ({parent.total_days}).'
                )
            parent_periods = list(parent.periods.all().order_by('start_date'))
            if len(periods) != len(parent_periods):
                raise ValidationError(
                    'Για ολική ανάκληση τα διαστήματα πρέπει να ταυτίζονται με την αρχική άδεια.'
                )
            for p, pp in zip(periods, parent_periods):
                if p['start_date'] != pp.start_date or p['end_date'] != pp.end_date:
                    raise ValidationError(
                        'Για ολική ανάκληση τα διαστήματα πρέπει να ταυτίζονται με την αρχική άδεια.'
                    )
        elif scope == 'PARTIAL':
            if days <= 0:
                raise ValidationError('Η μερική ανάκληση απαιτεί τουλάχιστον μία ημέρα.')
            if days >= remaining and not parent.revoked_days and days == parent.total_days:
                # Επιτρέπεται μερική που καλύπτει όλο — θα λειτουργήσει ως πλήρης στην ολοκλήρωση
                pass
            for i, period in enumerate(periods, 1):
                d = period['start_date']
                while d <= period['end_date']:
                    if not parent.date_covered_by_parent_periods(d):
                        raise ValidationError(
                            f'Διάστημα {i}: η ημερομηνία {d.isoformat()} δεν ανήκει '
                            f'στα διαστήματα της αρχικής άδειας.'
                        )
                    d = d + timedelta(days=1)

        return cleaned
