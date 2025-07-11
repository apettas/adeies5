#!/usr/bin/env python
"""
Script to create a Django superuser automatically
"""
import os
import django
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

User = get_user_model()

# Superuser credentials
email = 'admin@pdede.gr'
password = 'admin123'
first_name = 'Admin'
last_name = 'ΠΔΕΔΕ'

# Check if superuser already exists
if User.objects.filter(email=email).exists():
    print(f'Superuser με email {email} υπάρχει ήδη.')
    user = User.objects.get(email=email)
    print(f'Username: {user.email}')
    print(f'Όνομα: {user.first_name} {user.last_name}')
else:
    # Create superuser
    user = User.objects.create_superuser(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name
    )
    print(f'Superuser δημιουργήθηκε επιτυχώς!')
    print(f'Email: {email}')
    print(f'Password: {password}')
    print(f'Όνομα: {first_name} {last_name}')

print('\nΜπορείς να συνδεθείς στο admin panel στο: http://localhost/admin/')