"""
Utilities for regular leave balance ledger management
"""
from django.utils import timezone
from leaves.models import RegularLeaveBalanceEntry


def create_balance_entry(employee, entry_type, description, balance_after,
                        leave_request=None, days_delta=None, notes='', created_by=None,
                        balance_before=None):
    """
    Create a RegularLeaveBalanceEntry and update the cached balance on the user.

    If balance_before is not provided, it's computed from the last entry's
    balance_after (or the employee's current cached balance).

    Args:
        employee: User object
        entry_type: str (from ENTRY_TYPES choices)
        description: str
        balance_after: int — the balance after this entry (source of truth)
        leave_request: optional LeaveRequest
        days_delta: optional int (+for return, -for deduction)
        notes: optional str
        created_by: optional User
        balance_before: optional int — if omitted, computed automatically
    """
    if balance_before is None:
        last = get_last_balance(employee)
        balance_before = last if last is not None else employee.current_regular_leave_balance

    entry = RegularLeaveBalanceEntry.objects.create(
        employee=employee,
        entry_type=entry_type,
        entry_date=timezone.now().date(),
        description=description,
        balance_before=balance_before,
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


def get_balance_entries(employee, year=None):
    """
    Get balance entries for an employee, ordered by date descending.
    
    Args:
        employee: User object
        year: optional int — filter by calendar year (default: all years)
    """
    qs = RegularLeaveBalanceEntry.objects.filter(employee=employee)
    if year:
        qs = qs.filter(entry_date__year=year)
    return qs.order_by('-entry_date', '-created_at')


def finalize_entry(entry, verified_by):
    """
    Mark a ledger entry as finalized (cannot be modified).
    """
    from django.utils import timezone
    entry.is_finalized = True
    entry.verified_by = verified_by
    entry.verified_at = timezone.now()
    entry.save(update_fields=['is_finalized', 'verified_by', 'verified_at'])
    return entry