#!/usr/bin/env python
import os
import sys
import django

# Προσθήκη του directory στο Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ρύθμιση Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

# Εισαγωγή models
from accounts.models import User, Department, DepartmentType
from leaves.models import LeaveRequest, LeaveType
from django.contrib.auth.models import Group
from django.utils import timezone

def test_sdei_kedasy_workflow():
    """Τεστάρει τη λειτουργικότητα ΣΔΕΥ-ΚΕΔΑΣΥ"""
    
    print("🧪 Ξεκινά το τεστ της λειτουργικότητας ΣΔΕΥ-ΚΕΔΑΣΥ...")
    
    try:
        # Δημιουργία department types αν δεν υπάρχουν
        kedasy_type, _ = DepartmentType.objects.get_or_create(
            code='KEDASY',
            defaults={'name': 'ΚΕΔΑΣΥ'}
        )
        
        sdei_type, _ = DepartmentType.objects.get_or_create(
            code='SDEI',
            defaults={'name': 'ΣΔΕΥ'}
        )
        
        # Δημιουργία τμημάτων
        kedasy_dept = Department.objects.create(
            name='ΚΕΔΑΣΥ Τεστ',
            department_type=kedasy_type
        )
        
        sdei_dept = Department.objects.create(
            name='ΣΔΕΥ Τεστ',
            department_type=sdei_type,
            parent_department=kedasy_dept
        )
        
        # Δημιουργία ρόλων
        manager_group, _ = Group.objects.get_or_create(name='MANAGER')
        employee_group, _ = Group.objects.get_or_create(name='EMPLOYEE')
        
        # Δημιουργία χρηστών
        kedasy_manager = User.objects.create_user(
            username='kedasy_manager_test',
            first_name='Προϊστάμενος',
            last_name='ΚΕΔΑΣΥ',
            email='kedasy_manager_test@example.com',
            department=kedasy_dept,
            is_active=True
        )
        kedasy_manager.groups.add(manager_group)
        
        sdei_employee = User.objects.create_user(
            username='sdei_employee_test',
            first_name='Υπάλληλος',
            last_name='ΣΔΕΥ',
            email='sdei_employee_test@example.com',
            department=sdei_dept,
            is_active=True
        )
        sdei_employee.groups.add(employee_group)
        
        # Δημιουργία τύπου άδειας
        leave_type, _ = LeaveType.objects.get_or_create(
            name='Κανονική Άδεια',
            defaults={'requires_approval': True}
        )
        
        # Δημιουργία αίτησης άδειας από ΣΔΕΥ
        leave_request = LeaveRequest.objects.create(
            user=sdei_employee,
            leave_type=leave_type,
            description='Τεστ αίτηση από ΣΔΕΥ',
            status='SUBMITTED',
            submitted_at=timezone.now()
        )
        
        print(f"📊 Δημιουργήθηκε αίτηση #{leave_request.id} από {sdei_employee.username}")
        print(f"   Τμήμα: {sdei_dept.name} (parent: {sdei_dept.parent_department.name})")
        print(f"   Manager: {kedasy_manager.username} ({kedasy_dept.name})")
        
        # Τεστ 1: Έλεγχος αν ο ΚΕΔΑΣΥ manager βλέπει τον ΣΔΕΥ employee
        subordinates = kedasy_manager.get_subordinates()
        subordinate_usernames = [u.username for u in subordinates]
        print(f"\n🔍 Υφιστάμενοι ΚΕΔΑΣΥ manager: {subordinate_usernames}")
        
