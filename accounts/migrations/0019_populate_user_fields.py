# Generated by Django custom data migration

from django.db import migrations

def populate_user_fields(apps, schema_editor):
    """Προσθήκη κειμένων στα νέα πεδία των υπαρχόντων χρηστών"""
    User = apps.get_model('accounts', 'User')
    
    # Κείμενα που θα προστεθούν
    notification_text = "1. Ενδιαφερόμενη\n2. 2ο ΚΕΔΑΣΥ Αχαϊας\n3. ΔΔΕ Αχαϊας"
    user_description_text = 'Αναπληρώτρια ΕΕΠ κλάδου ΠΕ30 Κοινωνικών Λειτουργών που υπηρετεί στο ΣΔΕΥ/ Ειδικό Νηπιαγωγείο Αγρινίου "Μαρία Δημάδη"'
    
    # Ενημέρωση όλων των υπαρχόντων χρηστών
    updated_count = User.objects.all().update(
        notification=notification_text,
        user_description=user_description_text
    )
    
    print(f"Ενημερώθηκαν {updated_count} χρήστες με τα νέα πεδία")

def reverse_populate_user_fields(apps, schema_editor):
    """Αναίρεση της ενημέρωσης - καθαρισμός των πεδίων"""
    User = apps.get_model('accounts', 'User')
    
    User.objects.all().update(
        notification='',
        user_description=''
    )

class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0018_user_notification_user_user_description'),
    ]

    operations = [
        migrations.RunPython(
            populate_user_fields,
            reverse_populate_user_fields,
        ),
    ]