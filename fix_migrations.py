#!/usr/bin/env python
"""
Script to fix migration conflicts in the Django project.
This script will reset the migration state and create a clean migration.
"""

import os
import sys
import django
from django.core.management import execute_from_command_line

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

from django.db import connection
from django.core.management import call_command

def fix_migrations():
    """Fix migration conflicts by resetting migration state"""
    
    print("🔧 Fixing migration conflicts...")
    
    try:
        # Check if the gender column exists
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='accounts_user' AND column_name='gender';
            """)
            gender_exists = cursor.fetchone() is not None
        
        if gender_exists:
            print("✅ Gender column already exists, marking migration as applied...")
            
            # Mark the problematic migration as applied
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO django_migrations (app, name, applied) 
                    VALUES ('accounts', '0016_user_gender', NOW())
                    ON CONFLICT (app, name) DO NOTHING;
                """)
            
            print("✅ Migration 0016_user_gender marked as applied")
        
        # Now run all remaining migrations
        print("🔄 Running remaining migrations...")
        call_command('migrate', verbosity=2)
        
        print("✅ All migrations completed successfully!")
        
    except Exception as e:
        print(f"❌ Error fixing migrations: {e}")
        return False
    
    return True

if __name__ == '__main__':
    success = fix_migrations()
    sys.exit(0 if success else 1)