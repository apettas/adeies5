# Normalize legacy role codes to canonical uppercase set

from django.db import migrations

from accounts.role_constants import LEGACY_ROLE_CODE_MAP


def normalize_role_codes(apps, schema_editor):
    Role = apps.get_model('accounts', 'Role')
    User = apps.get_model('accounts', 'User')

    for old_code, new_code in LEGACY_ROLE_CODE_MAP.items():
        old_role = Role.objects.filter(code=old_code).first()
        if not old_role:
            continue

        new_role, _ = Role.objects.get_or_create(
            code=new_code,
            defaults={
                'name': old_role.name,
                'description': old_role.description,
                'is_active': old_role.is_active,
            },
        )

        for user in User.objects.filter(roles=old_role):
            user.roles.add(new_role)
            user.roles.remove(old_role)

        if old_role.pk != new_role.pk:
            old_role.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0035_merge_category_and_legacy_balance'),
    ]

    operations = [
        migrations.RunPython(normalize_role_codes, migrations.RunPython.noop),
    ]
