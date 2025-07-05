#!/usr/bin/env python3
"""
Script για εξαγωγή της δομής της βάσης δεδομένων
"""
import os
import sys
import django

# Setup Django
sys.path.append('/app' if os.path.exists('/app') else '.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

from django.apps import apps
from django.db import models

def get_database_schema():
    """Εξάγει τη δομή της βάσης δεδομένων"""
    
    print("=" * 80)
    print("ΑΝΑΛΥΤΙΚΗ ΔΟΜΗ ΒΑΣΗΣ ΔΕΔΟΜΕΝΩΝ")
    print("=" * 80)
    
    # Πάρε όλα τα models από όλες τις εφαρμογές
    all_models = apps.get_models()
    
    # Ομαδοποίηση ανά εφαρμογή
    apps_models = {}
    for model in all_models:
        app_label = model._meta.app_label
        if app_label not in apps_models:
            apps_models[app_label] = []
        apps_models[app_label].append(model)
    
    total_tables = 0
    total_fields = 0
    
    # Εμφάνιση ανά εφαρμογή
    for app_label, models_list in sorted(apps_models.items()):
        print(f"\n{'='*60}")
        print(f"ΕΦΑΡΜΟΓΗ: {app_label.upper()}")
        print(f"{'='*60}")
        
        for model in sorted(models_list, key=lambda x: x._meta.db_table):
            table_name = model._meta.db_table
            model_name = model.__name__
            
            print(f"\n📋 ΠΙΝΑΚΑΣ: {table_name}")
            print(f"   Model: {model_name}")
            print(f"   Verbose Name: {model._meta.verbose_name}")
            print(f"   Verbose Name Plural: {model._meta.verbose_name_plural}")
            
            # Πεδία
            fields = model._meta.get_fields()
            print(f"   Πεδία ({len(fields)}):")
            
            field_count = 0
            for field in fields:
                field_count += 1
                
                # Τύπος πεδίου
                field_type = type(field).__name__
                
                # Όνομα πεδίου
                field_name = field.name if hasattr(field, 'name') else str(field)
                
                # Verbose name
                verbose_name = ""
                if hasattr(field, 'verbose_name') and field.verbose_name:
                    verbose_name = f" ({field.verbose_name})"
                
                # Περιγραφή πεδίου
                field_info = f"      • {field_name}{verbose_name} - {field_type}"
                
                # Επιπλέον πληροφορίες
                extra_info = []
                
                if hasattr(field, 'max_length') and field.max_length:
                    extra_info.append(f"max_length={field.max_length}")
                
                if hasattr(field, 'null') and field.null:
                    extra_info.append("nullable")
                
                if hasattr(field, 'blank') and field.blank:
                    extra_info.append("blank")
                
                if hasattr(field, 'unique') and field.unique:
                    extra_info.append("unique")
                
                if hasattr(field, 'primary_key') and field.primary_key:
                    extra_info.append("PRIMARY KEY")
                
                if hasattr(field, 'default') and field.default != models.NOT_PROVIDED:
                    extra_info.append(f"default={field.default}")
                
                if hasattr(field, 'choices') and field.choices:
                    extra_info.append(f"choices={len(field.choices)}")
                
                # Foreign Key info
                if hasattr(field, 'related_model') and field.related_model:
                    extra_info.append(f"→ {field.related_model._meta.db_table}")
                
                if extra_info:
                    field_info += f" [{', '.join(extra_info)}]"
                
                print(field_info)
                
                # Εμφάνιση choices αν υπάρχουν
                if hasattr(field, 'choices') and field.choices and len(field.choices) <= 10:
                    print(f"        Choices: {dict(field.choices)}")
            
            total_tables += 1
            total_fields += field_count
            
            print(f"   └─ Συνολικά: {field_count} πεδία")
    
    print(f"\n{'='*80}")
    print(f"ΣΥΝΟΨΗ")
    print(f"{'='*80}")
    print(f"Συνολικά Εφαρμογές: {len(apps_models)}")
    print(f"Συνολικά Πίνακες: {total_tables}")
    print(f"Συνολικά Πεδία: {total_fields}")
    print(f"Μέσος όρος πεδίων ανά πίνακα: {total_fields/total_tables:.1f}")
    
    # Εμφάνιση σχέσεων
    print(f"\n{'='*60}")
    print("ΣΧΕΣΕΙΣ ΠΙΝΑΚΩΝ")
    print(f"{'='*60}")
    
    for app_label, models_list in sorted(apps_models.items()):
        for model in models_list:
            foreign_keys = [f for f in model._meta.get_fields() if f.__class__.__name__ == 'ForeignKey']
            many_to_many = [f for f in model._meta.get_fields() if f.__class__.__name__ == 'ManyToManyField']
            
            if foreign_keys or many_to_many:
                print(f"\n🔗 {model._meta.db_table}:")
                
                for fk in foreign_keys:
                    print(f"   ├─ {fk.name} → {fk.related_model._meta.db_table}")
                
                for m2m in many_to_many:
                    print(f"   ├─ {m2m.name} ⟷ {m2m.related_model._meta.db_table} (Many-to-Many)")

if __name__ == "__main__":
    get_database_schema()