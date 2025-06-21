from django import forms
from django.forms.widgets import DateInput


class GreekDateInput(forms.DateInput):
    """Custom widget για ελληνικές ημερομηνίες με format dd/mm/yyyy"""
    
    def __init__(self, attrs=None):
        default_attrs = {
            'class': 'form-control greek-datepicker',
            'placeholder': 'ηη/μμ/εεεε',
            'autocomplete': 'off'
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs, format='%d/%m/%Y')
    
    def format_value(self, value):
        """Μορφοποίηση της τιμής σε ελληνικό format"""
        if value:
            if isinstance(value, str):
                return value
            try:
                return value.strftime('%d/%m/%Y')
            except AttributeError:
                return str(value)
        return ''