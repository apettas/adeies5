from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0039_user_sso_cas_fields'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='hire_date',
        ),
    ]
