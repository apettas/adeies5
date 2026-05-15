"""
Utilities for regular leave balance ledger management
"""
from django.utils import timezone
from leaves.models import RegularLeaveBalanceEntry


def create_balance_entry(employee, entry_type, description, balance_after,
                        leave_request=None, days_delta=None, notes='', created_by=None):
    """
    Create a RegularLeaveBalanceEntry and update the cached balance on the user.
    
    Args:
        employee: User object
        entry_type: str (from ENTRY_TYPES choices)
        description: str
        balance_after: int — the balance after this entry (source of truth)
        leave_request: optional LeaveRequest
        days_delta: optional int (+for return, -for deduction)
        notes: optional str
        created_by: optional User
    """
    entry = RegularLeaveBalanceEntry.objects.create(
        employee=employee,
        entry_type=entry_type,
        entry_date=timezone.now().date(),
        description=description,
        balance_after=balance_after,
        leave_request=leave_request,
        days_delta=days_delta,
        notes=notes,
        created_by=created_by
    )
    
    # Update cached field on user
    employee.current_regular_leave_balance = balance_after
    employee.save(update_fields=['current_regular_leave_balance'])
    
    return entry


def get_last_balance(employee):
    """
    Get the last balance_after for an employee.
    Returns the last entry's balance_after, or None if no entries exist.
    """
    last_entry = RegularLeaveBalanceEntry.objects.filter(
        employee=employee
    ).order_by('-entry_date', '-created_at').first()
    
    if last_entry:
        return last_entry.balance_after
    return None


def get_balance_entries(employee):
    """
    Get all balance entries for an employee, ordered by date descending.
    """
    return RegularLeaveBalanceEntry.objects.filter(
        employee=employee
    ).order_by('-entry_date', '-created_at')
