# Generated manually to add missing foreign key fields
# This migration is a no-op since the fields already exist in the database

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0010_add_missing_decision_foreign_keys'),
    ]

    def do_nothing(apps, schema_editor):
        """No-op function since fields already exist"""
        pass

    operations = [
        migrations.RunPython(do_nothing, do_nothing),
    ]