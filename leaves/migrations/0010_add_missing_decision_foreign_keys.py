# Generated manually to add missing foreign key fields

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0009_add_decision_fields_to_leaverequest'),
    ]

    def check_and_add_field(apps, schema_editor, model_name, field_name, field):
        """Check if field exists before adding"""
        db_alias = schema_editor.connection.alias
        
        # Check if column exists
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'leaves_{model_name.lower()}' 
                AND column_name = '{field_name}_id'
            """)
            exists = cursor.fetchone()
            
        if not exists:
            # Column doesn't exist, add it
            model = apps.get_model('leaves', model_name)
            schema_editor.add_field(model, field)

    def reverse_check_and_remove_field(apps, schema_editor, model_name, field_name, field):
        """Remove field if it exists"""
        db_alias = schema_editor.connection.alias
        
        # Check if column exists
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'leaves_{model_name.lower()}' 
                AND column_name = '{field_name}_id'
            """)
            exists = cursor.fetchone()
            
        if exists:
            # Column exists, remove it
            model = apps.get_model('leaves', model_name)
            schema_editor.remove_field(model, field)

    def add_foreign_keys(apps, schema_editor):
        """Add foreign key fields if they don't exist"""
        
        # Define the fields
        logo_field = models.ForeignKey(
            'leaves.Logo',
            on_delete=django.db.models.deletion.SET_NULL,
            null=True,
            blank=True,
            verbose_name='Λογότυπο Απόφασης'
        )
        logo_field.set_attributes_from_name('decision_logo')
        
        info_field = models.ForeignKey(
            'leaves.Info',
            on_delete=django.db.models.deletion.SET_NULL,
            null=True,
            blank=True,
            verbose_name='Πληροφορίες Απόφασης'
        )
        info_field.set_attributes_from_name('decision_info')
        
        ypopsin_field = models.ForeignKey(
            'leaves.Ypopsin',
            on_delete=django.db.models.deletion.SET_NULL,
            null=True,
            blank=True,
            verbose_name='Υπογραφή Απόφασης'
        )
        ypopsin_field.set_attributes_from_name('decision_ypopsin')
        
        signee_field = models.ForeignKey(
            'leaves.Signee',
            on_delete=django.db.models.deletion.SET_NULL,
            null=True,
            blank=True,
            verbose_name='Υπογράφων Απόφασης'
        )
        signee_field.set_attributes_from_name('decision_signee')
        
        # Add each field if it doesn't exist
        check_and_add_field(apps, schema_editor, 'LeaveRequest', 'decision_logo', logo_field)
        check_and_add_field(apps, schema_editor, 'LeaveRequest', 'decision_info', info_field)
        check_and_add_field(apps, schema_editor, 'LeaveRequest', 'decision_ypopsin', ypopsin_field)
        check_and_add_field(apps, schema_editor, 'LeaveRequest', 'decision_signee', signee_field)

    def remove_foreign_keys(apps, schema_editor):
        """Remove foreign key fields if they exist"""
        
        # Define the fields for removal
        logo_field = models.ForeignKey(
            'leaves.Logo',
            on_delete=django.db.models.deletion.SET_NULL,
            null=True,
            blank=True,
            verbose_name='Λογότυπο Απόφασης'
        )
        logo_field.set_attributes_from_name('decision_logo')
        
        info_field = models.ForeignKey(
            'leaves.Info',
            on_delete=django.db.models.deletion.SET_NULL,
            null=True,
            blank=True,
            verbose_name='Πληροφορίες Απόφασης'
        )
        info_field.set_attributes_from_name('decision_info')
        
        ypopsin_field = models.ForeignKey(
            'leaves.Ypopsin',
            on_delete=django.db.models.deletion.SET_NULL,
            null=True,
            blank=True,
            verbose_name='Υπογραφή Απόφασης'
        )
        ypopsin_field.set_attributes_from_name('decision_ypopsin')
        
        signee_field = models.ForeignKey(
            'leaves.Signee',
            on_delete=django.db.models.deletion.SET_NULL,
            null=True,
            blank=True,
            verbose_name='Υπογράφων Απόφασης'
        )
        signee_field.set_attributes_from_name('decision_signee')
        
        # Remove each field if it exists
        reverse_check_and_remove_field(apps, schema_editor, 'LeaveRequest', 'decision_logo', logo_field)
        reverse_check_and_remove_field(apps, schema_editor, 'LeaveRequest', 'decision_info', info_field)
        reverse_check_and_remove_field(apps, schema_editor, 'LeaveRequest', 'decision_ypopsin', ypopsin_field)
        reverse_check_and_remove_field(apps, schema_editor, 'LeaveRequest', 'decision_signee', signee_field)

    operations = [
        migrations.RunPython(add_foreign_keys, remove_foreign_keys),
    ]