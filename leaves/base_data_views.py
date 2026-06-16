"""
Views for basic database data management.
Προβολή, προσθήκη, επεξεργασία και διαγραφή βασικών στοιχείων της βάσης.
Access: LEAVE_HANDLER, ADMIN, HR_ADMIN
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.db import models as db_models

from .base_data_config import (
    TABLE_REGISTRY,
    get_table_config,
    build_field_specs,
    get_list_field_specs,
    get_form_field_specs,
    get_field_raw_value,
    get_field_display_value,
)
from .models import PublicHoliday

User = get_user_model()

SENSITIVE_USER_FIELDS = {'is_superuser'}


class BaseDataPermissionMixin:
    """Έλεγχος δικαιώματος μετά το login."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not _user_can_manage_db(request.user):
            raise PermissionDenied("Δεν έχετε δικαίωμα διαχείρισης βασικών στοιχείων.")
        return super().dispatch(request, *args, **kwargs)


def _user_can_manage_db(user):
    """Έλεγχος δικαιώματος διαχείρισης βασικών στοιχείων."""
    if not user.is_authenticated:
        return False
    return (
        user.is_superuser
        or user.roles.filter(code__in=['LEAVE_HANDLER', 'ADMIN', 'HR_ADMIN']).exists()
    )


def _get_model_for_table(table_key):
    """Επιστρέφει (model_class, display_name) για τον πίνακα."""
    result = get_table_config(table_key)
    if not result:
        return None
    model_class, config = result
    return model_class, config['name']


def _filter_specs_for_user(specs, user):
    """Αποκρύπτει ευαίσθητα πεδία από μη superuser."""
    if user.is_superuser:
        return specs
    return [s for s in specs if s['name'] not in SENSITIVE_USER_FIELDS]


def _get_table_context(table_key, user):
    """Κοινό context για πίνακα."""
    result = get_table_config(table_key)
    if not result:
        return None
    model_class, config = result
    all_specs = build_field_specs(model_class, config)
    all_specs = _filter_specs_for_user(all_specs, user)
    return {
        'model_class': model_class,
        'config': config,
        'all_field_specs': all_specs,
        'list_field_specs': get_list_field_specs(all_specs),
        'form_field_specs': get_form_field_specs(all_specs),
        'm2m_fields': set(config.get('m2m_fields', set())),
    }


def _optimize_queryset(model_class, qs):
    """select_related / prefetch_related για γρηγορότερη εμφάνιση."""
    if model_class == User:
        return qs.select_related(
            'department', 'specialty', 'employee_type'
        ).prefetch_related('roles')
    if model_class.__name__ == 'Department':
        return qs.select_related(
            'department_type', 'parent_department', 'prefecture',
            'headquarters', 'manager',
        )
    return qs


def _parse_post_value(spec, request):
    """Μετατροπή τιμής POST σε κατάλληλο τύπο."""
    name = spec['name']
    field_type = spec['type']
    widget = spec['widget']

    if widget == 'multiselect':
        return request.POST.getlist(name)

    if field_type == 'ForeignKey':
        raw = request.POST.get(name, '').strip()
        if not raw:
            return None
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None

    if field_type in ('BooleanField', 'NullBooleanField'):
        return request.POST.get(name) in ('on', 'True', 'true', '1')

    raw = request.POST.get(name)
    if raw is None or raw == '':
        if field_type in (
            'IntegerField', 'PositiveIntegerField', 'PositiveSmallIntegerField',
            'SmallIntegerField', 'BigIntegerField', 'DecimalField', 'FloatField',
        ):
            return None
        if spec.get('blank') or field_type in ('TextField', 'CharField', 'EmailField'):
            return ''
        return None

    if field_type in (
        'IntegerField', 'PositiveIntegerField', 'PositiveSmallIntegerField',
        'SmallIntegerField', 'BigIntegerField',
    ):
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None

    if field_type in ('DecimalField', 'FloatField'):
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None

    return raw


def _build_field_data_from_post(request, form_specs, m2m_fields):
    """Δημιουργία dict πεδίων από POST (χωρίς M2M)."""
    field_data = {}
    m2m_data = {}
    for spec in form_specs:
        if spec.get('readonly'):
            continue
        name = spec['name']
        if name in m2m_fields:
            m2m_data[name] = _parse_post_value(spec, request)
            continue
        field_data[name] = _parse_post_value(spec, request)
    return field_data, m2m_data


def _apply_m2m(record, m2m_data, m2m_fields):
    """Εφαρμογή τιμών ManyToMany μετά το save."""
    for name, values in m2m_data.items():
        if name not in m2m_fields:
            continue
        manager = getattr(record, name)
        pks = [int(v) for v in values if str(v).strip()]
        manager.set(pks)


def _save_record(record, field_data, m2m_data, m2m_fields):
    """Αποθήκευση με full_clean και M2M."""
    for field_name, value in field_data.items():
        try:
            field = record._meta.get_field(field_name)
        except db_models.FieldDoesNotExist:
            setattr(record, field_name, value)
            continue
        if isinstance(field, db_models.ForeignKey):
            setattr(record, f'{field_name}_id', value)
        else:
            setattr(record, field_name, value)
    record.full_clean()
    record.save()
    _apply_m2m(record, m2m_data, m2m_fields)


class BaseDataIndexView(LoginRequiredMixin, BaseDataPermissionMixin, TemplateView):
    """Λίστα διαθέσιμων πινάκων για διαχείριση."""

    template_name = 'leaves/base_data_index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tables = [
            {
                'key': key,
                'name': cfg['name'],
                'icon': cfg['icon'],
            }
            for key, cfg in TABLE_REGISTRY.items()
        ]
        context['tables'] = tables
        return context


class BaseDataTableView(LoginRequiredMixin, BaseDataPermissionMixin, View):
    """Προβολή και CRUD εγγραφών συγκεκριμένου πίνακα."""

    template_name = 'leaves/base_data_table.html'

    def dispatch(self, request, *args, **kwargs):
        table_key = kwargs.get('table_key')
        ctx = _get_table_context(table_key, request.user)
        if not ctx:
            if request.user.is_authenticated:
                messages.error(request, 'Μη έγκυρος πίνακας.')
                return redirect('leaves:base_data_index')
            return super().dispatch(request, *args, **kwargs)

        self.table_key = table_key
        self.model_class = ctx['model_class']
        self.config = ctx['config']
        self.form_field_specs = ctx['form_field_specs']
        self.list_field_specs = ctx['list_field_specs']
        self.m2m_fields = ctx['m2m_fields']
        self.display_name = self.config['name']
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, table_key):
        records = _optimize_queryset(
            self.model_class,
            self.model_class.objects.all(),
        )
        context = {
            'table_key': table_key,
            'display_name': self.display_name,
            'model_name': self.model_class._meta.model_name,
            'records': records,
            'list_field_specs': self.list_field_specs,
            'form_field_specs': self.form_field_specs,
            'can_add': self.config.get('can_add', True),
            'can_delete': True,
            'can_edit': True,
        }
        return render(request, self.template_name, context)

    def post(self, request, table_key):
        action = request.POST.get('action')
        if action == 'add':
            return self._handle_add(request)
        if action == 'edit':
            return self._handle_edit(request)
        if action == 'delete':
            return self._handle_delete(request)
        messages.error(request, 'Μη έγκυρη ενέργεια.')
        return redirect('leaves:base_data_table', table_key=table_key)

    def _handle_add(self, request):
        table_key = self.table_key
        if not self.config.get('can_add', True):
            messages.error(request, 'Η προσθήκη εγγραφών δεν επιτρέπεται σε αυτόν τον πίνακα.')
            return redirect('leaves:base_data_table', table_key=table_key)

        field_data, m2m_data = _build_field_data_from_post(
            request, self.form_field_specs, self.m2m_fields,
        )
        if self.model_class == PublicHoliday:
            field_data['created_by'] = request.user.pk

        try:
            record = self.model_class()
            _save_record(record, field_data, m2m_data, self.m2m_fields)
            messages.success(request, 'Η εγγραφή προστέθηκε επιτυχώς.')
        except (ValidationError, ValueError, TypeError) as e:
            messages.error(request, f'Σφάλμα κατά την προσθήκη: {e}')
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την προσθήκη: {e}')
        return redirect('leaves:base_data_table', table_key=table_key)

    def _handle_edit(self, request):
        table_key = self.table_key
        record_id = request.POST.get('record_id')
        if not record_id:
            messages.error(request, 'Δεν επιλέχθηκε εγγραφή προς επεξεργασία.')
            return redirect('leaves:base_data_table', table_key=table_key)

        try:
            record = get_object_or_404(self.model_class, pk=record_id)
            field_data, m2m_data = _build_field_data_from_post(
                request, self.form_field_specs, self.m2m_fields,
            )
            _save_record(record, field_data, m2m_data, self.m2m_fields)
            messages.success(request, 'Η εγγραφή ενημερώθηκε επιτυχώς.')
        except (ValidationError, ValueError, TypeError) as e:
            messages.error(request, f'Σφάλμα κατά την επεξεργασία: {e}')
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την επεξεργασία: {e}')
        return redirect('leaves:base_data_table', table_key=table_key)

    def _handle_delete(self, request):
        table_key = self.table_key
        record_id = request.POST.get('record_id')
        if not record_id:
            messages.error(request, 'Δεν επιλέχθηκε εγγραφή προς διαγραφή.')
            return redirect('leaves:base_data_table', table_key=table_key)

        try:
            record = get_object_or_404(self.model_class, pk=record_id)
            record.delete()
            messages.success(request, 'Η εγγραφή διαγράφηκε επιτυχώς.')
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά τη διαγραφή: {e}')
        return redirect('leaves:base_data_table', table_key=table_key)


class GetRecordDataView(LoginRequiredMixin, BaseDataPermissionMixin, View):
    """AJAX endpoint για φόρτωση δεδομένων εγγραφής στην επεξεργασία."""

    def dispatch(self, request, *args, **kwargs):
        table_key = kwargs.get('table_key')
        ctx = _get_table_context(table_key, request.user)
        if not ctx:
            return JsonResponse({'error': 'Μη έγκυρος πίνακας'}, status=400)

        self.model_class = ctx['model_class']
        self.form_field_specs = ctx['form_field_specs']
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, table_key, record_id):
        try:
            record = get_object_or_404(self.model_class, pk=record_id)
            if self.model_class == User:
                record = _optimize_queryset(User, User.objects.filter(pk=record_id)).first()

            data = {'id': record.pk}
            for spec in self.form_field_specs:
                name = spec['name']
                data[name] = {
                    'label': spec['label'],
                    'type': spec['type'],
                    'widget': spec['widget'],
                    'value': get_field_raw_value(record, spec),
                    'display': get_field_display_value(record, spec),
                    'readonly': spec.get('readonly', False),
                }
            return JsonResponse(data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
