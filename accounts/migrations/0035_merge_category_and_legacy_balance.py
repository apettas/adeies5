# Generated manually — merge user_category into employee_type, drop legacy balance fields

from django.db import migrations, models


EMPLOYEE_TYPE_DEFAULTS = [
    {'code': 'ADMINISTRATIVE', 'name': 'Διοικητικοί', 'description': 'Μόνιμο διοικητικό προσωπικό'},
    {'code': 'EDUCATIONAL', 'name': 'Εκπαιδευτικοί', 'description': 'Μόνιμο εκπαιδευτικό προσωπικό'},
    {'code': 'SUBSTITUTE', 'name': 'Αναπληρωτές', 'description': 'Αναπληρωτές εκπαιδευτικοί'},
    {'code': 'SDEU_SUPPORT', 'name': 'Κέντρο Στήριξης ΣΔΕΥ', 'description': 'Υπεύθυνοι Κέντρου Στήριξης ΣΔΕΥ'},
    {'code': 'EDUCATION_DIRECTOR', 'name': 'Δ/ντες Εκπαίδευσης', 'description': 'Περιφερειακός Διευθυντής'},
    {'code': 'OTHER', 'name': 'Άλλο', 'description': 'Άλλες κατηγορίες'},
]

NAME_TO_CODE = {item['name']: item['code'] for item in EMPLOYEE_TYPE_DEFAULTS}


def populate_employee_types(apps, schema_editor):
    EmployeeType = apps.get_model('accounts', 'EmployeeType')

    for item in EMPLOYEE_TYPE_DEFAULTS:
        emp_type, _ = EmployeeType.objects.get_or_create(
            name=item['name'],
            defaults={
                'code': item['code'],
                'description': item['description'],
                'is_active': True,
            },
        )
        if emp_type.code != item['code']:
            emp_type.code = item['code']
            emp_type.save(update_fields=['code'])

    for emp_type in EmployeeType.objects.all():
        if not emp_type.code:
            emp_type.code = NAME_TO_CODE.get(emp_type.name, f'OTHER_{emp_type.pk}')
            emp_type.save(update_fields=['code'])


def migrate_user_category_to_employee_type(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    EmployeeType = apps.get_model('accounts', 'EmployeeType')

    for user in User.objects.exclude(user_category='').exclude(user_category__isnull=True):
        if user.employee_type_id:
            continue
        emp_type = EmployeeType.objects.filter(code=user.user_category).first()
        if emp_type is None:
            emp_type = EmployeeType.objects.filter(code='OTHER').first()
        if emp_type:
            user.employee_type = emp_type
            user.save(update_fields=['employee_type'])


def sync_regular_balance_from_legacy(apps, schema_editor):
    User = apps.get_model('accounts', 'User')

    for user in User.objects.all():
        legacy_total = (user.carryover_leave_days or 0) + (user.current_year_leave_balance or 0)
        total = user.leave_balance if user.leave_balance else legacy_total
        if total and user.current_regular_leave_balance != total:
            user.current_regular_leave_balance = total
            user.save(update_fields=['current_regular_leave_balance'])


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('accounts', '0034_remove_unused_model_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='employeetype',
            name='code',
            field=models.CharField(max_length=30, null=True, unique=True, verbose_name='Κωδικός'),
        ),
        migrations.RunPython(populate_employee_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='employeetype',
            name='code',
            field=models.CharField(max_length=30, unique=True, verbose_name='Κωδικός'),
        ),
        migrations.RunPython(migrate_user_category_to_employee_type, migrations.RunPython.noop),
        migrations.RunPython(sync_regular_balance_from_legacy, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='user',
            name='user_category',
        ),
        migrations.RemoveField(
            model_name='user',
            name='carryover_leave_days',
        ),
        migrations.RemoveField(
            model_name='user',
            name='current_year_leave_balance',
        ),
        migrations.RemoveField(
            model_name='user',
            name='leave_balance',
        ),
    ]
