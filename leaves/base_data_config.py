"""
Ρυθμίσεις πινάκων και πεδίων για τη διαχείριση βασικών στοιχείων (/leaves/base-data/).
"""
from django.db import models as db_models

from accounts.models import (
    User, Department, DepartmentType, Role, Specialty,
    Headquarters, Prefecture, EmployeeType,
)
from leaves.models import Logo, Info, Ypopsin, Signee, LeaveType, PublicHoliday

# Πεδία που δεν εμφανίζονται ποτέ στη φόρμα
GLOBAL_EXCLUDE = {
    'password', 'groups', 'user_permissions', 'logentry',
}

# Επιλογές για πεδία χωρίς choices στο μοντέλο
EXTRA_CHOICES = {
    'LeaveType.workflow_variant': [
        ('STANDARD', 'STANDARD'),
        ('KEDASY', 'KEDASY'),
        ('SDEY', 'SDEY'),
    ],
}

TABLE_REGISTRY = {
    'users': {
        'model': User,
        'name': 'Χρήστες',
        'icon': 'bi-people',
        'can_add': False,
        'readonly_fields': {
            'registration_date', 'approval_date', 'last_login', 'date_joined',
        },
        'exclude_fields': GLOBAL_EXCLUDE | {'approved_by'},
        'list_fields': [
            'last_name', 'first_name', 'email', 'department', 'employee_type',
            'specialty', 'registration_status', 'is_active',
        ],
        'm2m_fields': {'roles'},
    },
    'departments': {
        'model': Department,
        'name': 'Τμήματα',
        'icon': 'bi-diagram-3',
        'readonly_fields': {'created_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'department_types': {
        'model': DepartmentType,
        'name': 'Τύποι Τμημάτων',
        'icon': 'bi-building',
        'readonly_fields': {'created_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'roles': {
        'model': Role,
        'name': 'Ρόλοι',
        'icon': 'bi-shield',
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'employee_types': {
        'model': EmployeeType,
        'name': 'Τύποι Υπαλλήλων',
        'icon': 'bi-person-badge',
        'readonly_fields': {'created_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'specialties': {
        'model': Specialty,
        'name': 'Ειδικότητες',
        'icon': 'bi-bookmark-check',
        'readonly_fields': {'created_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'prefectures': {
        'model': Prefecture,
        'name': 'Νομοί',
        'icon': 'bi-geo-alt',
        'readonly_fields': {'created_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'headquarters': {
        'model': Headquarters,
        'name': 'Έδρες',
        'icon': 'bi-pin-map',
        'readonly_fields': {'created_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'logos': {
        'model': Logo,
        'name': 'Λογότυπα',
        'icon': 'bi-image',
        'readonly_fields': {'created_at', 'updated_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'infos': {
        'model': Info,
        'name': 'Πληροφορίες',
        'icon': 'bi-info-circle',
        'readonly_fields': {'created_at', 'updated_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'leave_types': {
        'model': LeaveType,
        'name': 'Τύποι Αδειών',
        'icon': 'bi-card-list',
        'readonly_fields': {'created_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'signees': {
        'model': Signee,
        'name': 'Υπογράφοντες',
        'icon': 'bi-pen',
        'readonly_fields': {'created_at', 'updated_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'ypopsins': {
        'model': Ypopsin,
        'name': 'Έχοντας Υπόψη',
        'icon': 'bi-eye',
        'readonly_fields': {'created_at', 'updated_at'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
    'public_holidays': {
        'model': PublicHoliday,
        'name': 'Δημόσιες Αργίες',
        'icon': 'bi-calendar-event',
        'readonly_fields': {'created_at', 'created_by'},
        'exclude_fields': GLOBAL_EXCLUDE,
    },
}


def get_table_config(table_key):
    """Επιστρέφει (model_class, config_dict) ή None."""
    config = TABLE_REGISTRY.get(table_key)
    if not config:
        return None
    return config['model'], config


def _choice_key(model_class, field_name):
    return f'{model_class.__name__}.{field_name}'


def _get_widget_type(field, field_type):
    if field_type == 'ManyToManyField':
        return 'multiselect'
    if field_type == 'ForeignKey':
        return 'select'
    if field_type in ('BooleanField', 'NullBooleanField'):
        return 'checkbox'
    if field_type == 'TextField':
        return 'textarea'
    if getattr(field, 'choices', None):
        return 'select'
    if field_type == 'DateField':
        return 'date'
    if field_type == 'DateTimeField':
        return 'datetime'
    return 'text'


def _get_fk_choices(field):
    related_model = field.related_model
    qs = related_model.objects.all()
    if related_model.__name__ == 'User':
        qs = qs.order_by('last_name', 'first_name')
    elif hasattr(related_model._meta, 'ordering') and related_model._meta.ordering:
        qs = qs.order_by(*related_model._meta.ordering)
    else:
        qs = qs.order_by('pk')
    choices = [('', '—')]
    for obj in qs[:500]:
        choices.append((str(obj.pk), str(obj)))
    return choices


def build_field_specs(model_class, config):
    """Δημιουργεί λίστα field specs για φόρμες και πίνακα."""
    exclude = set(config.get('exclude_fields', GLOBAL_EXCLUDE))
    readonly = set(config.get('readonly_fields', set()))
    m2m_fields = set(config.get('m2m_fields', set()))
    list_fields = config.get('list_fields')
    specs_by_name = {}

    for field in model_class._meta.get_fields():
        if field.name in exclude:
            continue
        if isinstance(field, db_models.ManyToManyField):
            if field.name not in m2m_fields and field.name not in exclude:
                continue
            spec = {
                'name': field.name,
                'label': field.verbose_name,
                'type': 'ManyToManyField',
                'widget': 'multiselect',
                'readonly': field.name in readonly,
                'choices': _get_fk_choices(field),
                'blank': field.blank,
            }
            specs_by_name[field.name] = spec
            continue

        if isinstance(field, (db_models.OneToOneField, db_models.ManyToOneRel, db_models.ManyToManyRel)):
            continue
        if isinstance(field, db_models.ForeignKey):
            spec = {
                'name': field.name,
                'label': field.verbose_name,
                'type': 'ForeignKey',
                'widget': 'select',
                'readonly': field.name in readonly,
                'choices': _get_fk_choices(field),
                'blank': field.null or field.blank,
            }
            specs_by_name[field.name] = spec
            continue

        if field.is_relation or field.primary_key:
            continue
        if getattr(field, 'auto_now_add', False) or getattr(field, 'auto_now', False):
            if field.name not in readonly:
                readonly.add(field.name)

        field_type = field.get_internal_type()
        if field_type not in (
            'CharField', 'TextField', 'IntegerField', 'BooleanField',
            'DateField', 'DateTimeField', 'EmailField', 'PositiveIntegerField',
            'PositiveSmallIntegerField', 'SmallIntegerField', 'BigIntegerField',
            'DecimalField', 'FloatField', 'URLField', 'SlugField',
            'NullBooleanField',
        ):
            continue

        choice_key = _choice_key(model_class, field.name)
        choices = list(field.choices) if getattr(field, 'choices', None) else None
        if choices is None and choice_key in EXTRA_CHOICES:
            choices = EXTRA_CHOICES[choice_key]

        widget = _get_widget_type(field, field_type)
        if choices and widget == 'text':
            widget = 'select'

        spec = {
            'name': field.name,
            'label': field.verbose_name,
            'type': field_type,
            'widget': widget,
            'readonly': field.name in readonly,
            'choices': choices,
            'blank': getattr(field, 'blank', False),
            'help_text': getattr(field, 'help_text', '') or '',
        }
        specs_by_name[field.name] = spec

    if list_fields:
        ordered = []
        for name in list_fields:
            if name in specs_by_name:
                ordered.append(specs_by_name[name])
        for name, spec in specs_by_name.items():
            if name not in list_fields:
                ordered.append(spec)
        return ordered

    return list(specs_by_name.values())


def get_list_field_specs(all_specs):
    """Πεδία για στήλες πίνακα (συμπεριλαμβανομένων readonly)."""
    return [s for s in all_specs if not s.get('widget') == 'textarea' or s['name'] in (
        'subject_text', 'decision_text', 'instructions', 'logo', 'info', 'ypopsin', 'signee',
        'description', 'role_description', 'notification_recipients',
    )][:12] or all_specs[:8]


def get_form_field_specs(all_specs):
    """Πεδία για φόρμες add/edit."""
    return all_specs


def get_field_display_value(record, spec):
    """Τιμή εμφάνισης πεδίου στον πίνακα."""
    name = spec['name']
    field_type = spec['type']

    if field_type == 'ManyToManyField':
        manager = getattr(record, name)
        return ', '.join(str(x) for x in manager.all()) or None

    if field_type == 'ForeignKey':
        obj = getattr(record, name, None)
        return str(obj) if obj else None

    value = getattr(record, name, None)
    if value is None or value == '':
        return None
    if field_type in ('BooleanField', 'NullBooleanField'):
        return value
    if spec.get('choices'):
        choices_dict = dict(spec['choices'])
        return choices_dict.get(value, value)
    if field_type == 'DateField' and hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y')
    if field_type == 'DateTimeField' and hasattr(value, 'strftime'):
        return value.strftime('%d/%m/%Y %H:%M')
    if field_type == 'TextField':
        text = str(value)
        return text if len(text) <= 80 else text[:77] + '...'
    return value


def get_field_raw_value(record, spec):
    """Τιμή για φόρμα επεξεργασίας (AJAX)."""
    name = spec['name']
    field_type = spec['type']

    if field_type == 'ManyToManyField':
        return list(getattr(record, name).values_list('pk', flat=True))

    if field_type == 'ForeignKey':
        obj = getattr(record, name, None)
        return str(obj.pk) if obj else ''

    value = getattr(record, name, None)
    if value is None:
        return ''
    if field_type in ('BooleanField', 'NullBooleanField'):
        return value
    if field_type == 'DateTimeField' and hasattr(value, 'isoformat'):
        return value.strftime('%Y-%m-%dT%H:%M')
    if field_type == 'DateField' and hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)
