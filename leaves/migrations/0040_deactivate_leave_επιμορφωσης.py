from django.db import migrations


def deactivate_επιμορφωσης(apps, schema_editor):
    LeaveType = apps.get_model('leaves', 'LeaveType')
    LeaveType.objects.filter(name='Άδεια Επιμόρφωσης').update(
        is_active=False,
        is_simple=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0039_add_requested_days'),
    ]

    operations = [
        migrations.RunPython(deactivate_επιμορφωσης, reverse_code=migrations.RunPython.noop),
    ]