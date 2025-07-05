# Generated manually for populating decision content tables

from django.db import migrations

def populate_decision_content_data(apps, schema_editor):
    """Προσθέτει τα αρχικά δεδομένα στους πίνακες για το περιεχόμενο των αποφάσεων"""
    
    Logo = apps.get_model('leaves', 'Logo')
    Info = apps.get_model('leaves', 'Info')
    Ypopsin = apps.get_model('leaves', 'Ypopsin')
    Signee = apps.get_model('leaves', 'Signee')
    
    # Δημιουργία Logo
    Logo.objects.create(
        logo_short="ΤΡΕΧΟΝ 2025",
        logo="""ΕΛΛΗΝΙΚΗ ΔΗΜΟΚΡΑΤΙΑ
ΥΠΟΥΡΓΕΙΟ ΠΑΙΔΕΙΑΣ, ΘΡΗΣΚΕΥΜΑΤΩΝ ΚΑΙ ΑΘΛΗΤΙΣΜΟΥ
ΠΕΡΙΦΕΡΕΙΑΚΗ ΔΙΕΥΘΥΝΣΗ
Π/ΘΜΙΑΣ & Δ/ΘΜΙΑΣ ΕΚΠΑΙΔΕΥΣΗΣ ΔΥΤΙΚΗΣ ΕΛΛΑΔΑΣ
ΑΥΤΟΤΕΛΗΣ ΔΙΕΥΘΥΝΣΗ ΔΙΟΙΚΗΤΙΚΗΣ,
ΟΙΚΟΝΟΜΙΚΗΣ ΚΑΙ ΠΑΙΔΑΓΩΓΙΚΗΣ ΥΠΟΣΤΗΡΙΞΗΣ
ΤΜΗΜΑ Γ' ΠΡΟΣΩΠΙΚΟΥ""",
        is_active=True
    )
    
    # Δημιουργία Info
    Info.objects.create(
        info_short="Κορσιάνου Αικατερίνη",
        info="""Ταχ. διεύθυνση : Ακτής Δυμαίων 25α, Πάτρα
Ταχ. κώδικας : 26222
Ταχ. θυρίδα : 2540
Πληροφορίες : Α. Κορσιάνου
Τηλέφωνο : 2610–362423
Ηλ. Ταχυδρομείο : pdede@sch.gr""",
        is_active=True
    )
    
    # Δημιουργία Ypopsin
    Ypopsin.objects.create(
        ypopsin_short="ΑΔΕΙΑ ΜΗΤΡΟΤΗΤΑΣ (Αναπληρωτές) 2022",
        ypopsin="""1.	Τις διατάξεις του άρθρου 9 του ν. 2224/1994
2.	Τις διατάξεις του άρθρου 14, παρ.29, περ. ε΄ του Ν. 2817/2000 (ΦΕΚ78/Α΄/14-03-2000).
3.	Τις διατάξεις του άρθρου 11 του ν. 2874/2000
4.	Το Π.Δ 18/2018 (ΦΕΚ τ. Α΄31/23-2-18) «Οργανισμός Υπουργείου Παιδείας, Έρευνας και Θρησκευμάτων.
5.	Τις διατάξεις του άρθρου 34 του ν. 4808/2021
6. Την αριθμ. πρωτ. Φ.350.2/12/95133/Ε3/29-07-2022 (ΑΔΑ: 6ΧΤΥ46ΜΤΛΗ-ΥΨΨ) Απόφαση της Προϊσταμένης της Γενικής Διεύθυνσης Εκπαιδευτικού Προσωπικού Πρωτοβάθμιας και Δευτεροβάθμιας Εκπαίδευσης του Υπουργείου Παιδείας και Θρησκευμάτων «Ορισμός αναπληρωτών των Περιφερειακών Διευθυντών Εκπαίδευσης».""",
        is_active=True
    )
    
    # Δημιουργία Signee
    Signee.objects.create(
        signee_short="Δελέγκος 2024",
        signee_name="Νικόλαος Δελέγκος",
        signee="Ο Αναπληρωτής Περιφερειακός Δ/ντής Π/θμιας & Δ/θμιας Εκπ/σης Δυτ. Ελλάδας",
        is_active=True
    )

def reverse_populate_decision_content_data(apps, schema_editor):
    """Αναίρεση της προσθήκης δεδομένων"""
    Logo = apps.get_model('leaves', 'Logo')
    Info = apps.get_model('leaves', 'Info')
    Ypopsin = apps.get_model('leaves', 'Ypopsin')
    Signee = apps.get_model('leaves', 'Signee')
    
    # Διαγραφή των αρχικών δεδομένων
    Logo.objects.filter(logo_short="ΤΡΕΧΟΝ 2025").delete()
    Info.objects.filter(info_short="Κορσιάνου Αικατερίνη").delete()
    Ypopsin.objects.filter(ypopsin_short="ΑΔΕΙΑ ΜΗΤΡΟΤΗΤΑΣ (Αναπληρωτές) 2022").delete()
    Signee.objects.filter(signee_short="Δελέγκος 2024").delete()

class Migration(migrations.Migration):

    dependencies = [
        ('leaves', '0007_create_decision_content_tables'),
    ]

    operations = [
        migrations.RunPython(
            populate_decision_content_data,
            reverse_populate_decision_content_data
        ),
    ]