"""
Views for basic database data management.
Προβολή, προσθήκη, επεξεργασία και διαγραφή βασικών στοιχείων της βάσης.
Access: LEAVE_HANDLER, ADMIN, HR_ADMIN
"""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import ListView, CreateView, DeleteView, TemplateView
from django.views import View
from django.http import HttpResponseRedirect, JsonResponse
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.db import models as db_models

from .models import Logo, Info, Ypopsin, Signee, LeaveType
from accounts.models import DepartmentType, EmployeeType, Specialty

User = get_user_model()


def _user_can_manage_db(user):
    """Check if user has permission to manage base data."""
    return (
        user.is_superuser or
        user.roles.filter(code__in=['LEAVE_HANDLER', 'ADMIN', 'HR_ADMIN']).exists()
    )


def _get_model_for_table(table_key):
    """Return (model_class, display_name) for the given table key."""
    tables = {
        'users': (User, 'Χρήστες'),
        'department_types': (DepartmentType, 'Τύποι Τμημάτων'),
        'employee_types': (EmployeeType, 'Τύποι Υπαλλήλων'),
        'specialties': (Specialty, 'Ειδικότητες'),
        'logos': (Logo, 'Λογότυπα'),
        'infos': (Info, 'Πληροφορίες'),
        'leave_types': (LeaveType, 'Τύποι Αδειών'),
        'signees': (Signee, 'Υπογράφοντες'),
        'ypopsins': (Ypopsin, 'Έχοντας Υπόψη'),
    }
    return tables.get(table_key)


def _get_table_display_name(model_class):
    """Get the verbose_name_plural for a model."""
    return model_class._meta.verbose_name_plural


def _get_fields_for_model(model_class, for_edit=False):
    """
    Return a list of (field_name, field_verbose_name, field_type) tuples.
    Excludes auto-generated fields like id, auto_now fields, relations.
    If for_edit=True, also include is_active, is_active fields are included.
    """
    exclude_fields = ['id', 'user', 'employee', 'leave_request']
    
    # For User model, we show specific fields only in view mode
    if model_class == User:
        return [
            ('last_name', 'Επίθετο', 'CharField'),
            ('first_name', 'Όνομα', 'CharField'),
            ('email', 'Email', 'EmailField'),
            ('is_active', 'Ενεργός', 'BooleanField'),
        ]
    
    fields = []
    for field in model_class._meta.get_fields():
        if field.is_relation or field.primary_key:
            continue
        if field.name in exclude_fields:
            continue
        # Skip auto_now_add and auto_now fields
        if getattr(field, 'auto_now_add', False) or getattr(field, 'auto_now', False):
            continue
        # Skip OneToOneField, ManyToManyField
        if isinstance(field, (db_models.OneToOneField, db_models.ManyToManyField)):
            continue
        
        field_type = field.get_internal_type()
        
        # Only include basic field types
        if field_type in ('CharField', 'TextField', 'IntegerField', 'BooleanField',
                          'DateField', 'DateTimeField', 'EmailField', 'PositiveIntegerField',
                          'PositiveSmallIntegerField', 'SmallIntegerField', 'BigIntegerField',
                          'DecimalField', 'FloatField', 'URLField', 'SlugField',
                          'BinaryField', 'GenericIPAddressField', 'IPAddressField',
                          'NullBooleanField'):
            fields.append((field.name, field.verbose_name, field_type))
    
    return fields


def _get_field_value(record, field_name, field_type):
    """Get the display value of a field for a record."""
    value = getattr(record, field_name, None)
    
    if value is None or value == '':
        return '', ''
    
    if field_type in ('BooleanField', 'NullBooleanField'):
        if value is None:
            return '', ''
        return value, value
    
    if field_type in ('DateField', 'DateTimeField'):
        if hasattr(value, 'strftime'):
            formatted = value.strftime('%d/%m/%Y %H:%M')
            iso = value.isoformat() if hasattr(value, 'isoformat') else str(value)
            return formatted, iso
        return str(value), str(value)
    
    return str(value), str(value)


class BaseDataIndexView(LoginRequiredMixin, TemplateView):
    """View that lists all available tables for management."""
    template_name = 'leaves/base_data_index.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not _user_can_manage_db(request.user):
            raise PermissionDenied("Δεν έχετε δικαίωμα διαχείρισης βασικών στοιχείων.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tables = [
            {'key': 'users', 'name': 'Χρήστες', 'icon': 'bi-people'},
            {'key': 'department_types', 'name': 'Τύποι Τμημάτων', 'icon': 'bi-building'},
            {'key': 'employee_types', 'name': 'Τύποι Υπαλλήλων', 'icon': 'bi-person-badge'},
            {'key': 'specialties', 'name': 'Ειδικότητες', 'icon': 'bi-bookmark-check'},
            {'key': 'logos', 'name': 'Λογότυπα', 'icon': 'bi-image'},
            {'key': 'infos', 'name': 'Πληροφορίες', 'icon': 'bi-info-circle'},
            {'key': 'leave_types', 'name': 'Τύποι Αδειών', 'icon': 'bi-card-list'},
            {'key': 'signees', 'name': 'Υπογράφοντες', 'icon': 'bi-pen'},
            {'key': 'ypopsins', 'name': 'Έχοντας Υπόψη', 'icon': 'bi-eye'},
        ]
        context['tables'] = tables
        return context


class BaseDataTableView(LoginRequiredMixin, View):
    """View that displays records of a specific table and allows CRUD operations."""
    template_name = 'leaves/base_data_table.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not _user_can_manage_db(request.user):
            raise PermissionDenied("Δεν έχετε δικαίωμα διαχείρισης βασικών στοιχείων.")
        
        table_key = kwargs.get('table_key')
        result = _get_model_for_table(table_key)
        if not result:
            messages.error(request, 'Μη έγκυρος πίνακας.')
            return redirect('leaves:base_data_index')
        
        self.model_class, self.display_name = result
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, table_key):
        records = self.model_class.objects.all()
        
        # For User model, select related department and prefetch roles
        if self.model_class == User:
            records = records.select_related('department', 'specialty', 'employee_type').prefetch_related('roles')
        
        fields = _get_fields_for_model(self.model_class)
        
        context = {
            'table_key': table_key,
            'display_name': self.display_name,
            'model_name': self.model_class._meta.model_name,
            'records': records,
            'fields': fields,
            'can_add': self.model_class != User,
            'can_delete': True,
            'can_edit': True,
        }
        return render(request, self.template_name, context)
    
    def post(self, request, table_key):
        action = request.POST.get('action')
        
        if action == 'add':
            return self._handle_add(request)
        elif action == 'edit':
            return self._handle_edit(request)
        elif action == 'delete':
            return self._handle_delete(request)
        
        messages.error(request, 'Μη έγκυρη ενέργεια.')
        return redirect('leaves:base_data_table', table_key=table_key)
    
    def _get_editable_fields(self):
        """Get all fields that can be edited (excludes pk, auto_now, relations)."""
        fields = []
        for field in self.model_class._meta.get_fields():
            if field.is_relation or field.primary_key:
                continue
            if getattr(field, 'auto_now_add', False) or getattr(field, 'auto_now', False):
                continue
            if isinstance(field, (db_models.OneToOneField, db_models.ManyToManyField)):
                continue
            fields.append(field)
        return fields
    
    def _build_field_data_from_post(self, request):
        """Build field data dictionary from POST data."""
        field_data = {}
        for field in self._get_editable_fields():
            value = request.POST.get(field.name)
            if value is not None:
                field_type = field.get_internal_type()
                
                if field_type in ('BooleanField', 'NullBooleanField'):
                    field_data[field.name] = (value == 'on' or value == 'True')
                elif field_type in ('IntegerField', 'PositiveIntegerField', 'PositiveSmallIntegerField',
                                   'SmallIntegerField', 'BigIntegerField'):
                    try:
                        field_data[field.name] = int(value) if value else None
                    except (ValueError, TypeError):
                        field_data[field.name] = None
                elif field_type in ('DecimalField', 'FloatField'):
                    try:
                        field_data[field.name] = float(value) if value else None
                    except (ValueError, TypeError):
                        field_data[field.name] = None
                else:
                    field_data[field.name] = value
        
        return field_data
    
    def _handle_add(self, request):
        """Handle adding a new record."""
        table_key = self.kwargs.get('table_key')
        
        if self.model_class == User:
            messages.error(request, 'Η προσθήκη χρηστών γίνεται μέσω εγγραφής.')
            return redirect('leaves:base_data_table', table_key=table_key)
        
        field_data = self._build_field_data_from_post(request)
        
        try:
            self.model_class.objects.create(**field_data)
            messages.success(request, 'Η εγγραφή προστέθηκε επιτυχώς.')
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την προσθήκη: {str(e)}')
        
        return redirect('leaves:base_data_table', table_key=table_key)
    
    def _handle_edit(self, request):
        """Handle editing an existing record."""
        table_key = self.kwargs.get('table_key')
        record_id = request.POST.get('record_id')
        
        if not record_id:
            messages.error(request, 'Δεν επιλέχθηκε εγγραφή προς επεξεργασία.')
            return redirect('leaves:base_data_table', table_key=table_key)
        
        try:
            record = get_object_or_404(self.model_class, pk=record_id)
            field_data = self._build_field_data_from_post(request)
            
            for field_name, value in field_data.items():
                setattr(record, field_name, value)
            
            record.save()
            messages.success(request, 'Η εγγραφή ενημερώθηκε επιτυχώς.')
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την επεξεργασία: {str(e)}')
        
        return redirect('leaves:base_data_table', table_key=table_key)
    
    def _handle_delete(self, request):
        """Handle deleting a record."""
        table_key = self.kwargs.get('table_key')
        record_id = request.POST.get('record_id')
        
        if not record_id:
            messages.error(request, 'Δεν επιλέχθηκε εγγραφή προς διαγραφή.')
            return redirect('leaves:base_data_table', table_key=table_key)
        
        try:
            record = get_object_or_404(self.model_class, pk=record_id)
            record.delete()
            messages.success(request, 'Η εγγραφή διαγράφηκε επιτυχώς.')
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά τη διαγραφή: {str(e)}')
        
        return redirect('leaves:base_data_table', table_key=table_key)


class GetRecordDataView(LoginRequiredMixin, View):
    """AJAX endpoint to get record data for editing."""
    
    def dispatch(self, request, *args, **kwargs):
        if not _user_can_manage_db(request.user):
            return JsonResponse({'error': 'Δεν έχετε δικαίωμα'}, status=403)
        
        table_key = kwargs.get('table_key')
        result = _get_model_for_table(table_key)
        if not result:
            return JsonResponse({'error': 'Μη έγκυρος πίνακας'}, status=400)
        
        self.model_class, self.display_name = result
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, table_key, record_id):
        try:
            record = get_object_or_404(self.model_class, pk=record_id)
            fields = _get_fields_for_model(self.model_class)
            
            data = {'id': record.pk}
            for field_name, field_label, field_type in fields:
                display_value, raw_value = _get_field_value(record, field_name, field_type)
                data[field_name] = {
                    'label': field_label,
                    'type': field_type,
                    'value': raw_value,
                    'display': display_value,
                }
            
            return JsonResponse(data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)