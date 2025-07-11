# Generated manually to add missing final_decision_text field
# This migration is a no-op since the field already exists in the database

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0011_add_decision_foreign_keys_simple'),
    ]

    def do_nothing(apps, schema_editor):
        """No-op function since field already exists"""
        pass

    operations = [
        migrations.RunPython(do_nothing, do_nothing),
    ]