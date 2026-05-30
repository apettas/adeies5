"""
Views for regular leave balance ledger
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.contrib.auth import get_user_model
from leaves.models import RegularLeaveBalanceEntry
from leaves.utils.balance_ledger import create_balance_entry

User = get_user_model()


@login_required
def balance_ledger_view(request, user_id):
    """
    View the balance ledger for a user with optional year filtering.
    - Users can view their own ledger
    - Handlers and admins can view any user's ledger
    - Default filter: current year
    """
    target_user = get_object_or_404(User, pk=user_id)
    
    if request.user != target_user and not request.user.is_leave_handler and not request.user.is_administrator:
        raise PermissionDenied("Δεν έχετε δικαίωμα προβολής αυτού του υπολοίπου.")
    
    year = request.GET.get('year', '')
    try:
        year = int(year) if year else timezone.now().year
    except (ValueError, TypeError):
        year = timezone.now().year
    
    entries = RegularLeaveBalanceEntry.objects.filter(
        employee=target_user,
        entry_date__year=year
    ).select_related('leave_request', 'created_by').order_by('-entry_date', '-created_at')
    
    last_entry = entries.first()
    current_balance = last_entry.balance_after if last_entry else target_user.current_regular_leave_balance
    
    available_years = RegularLeaveBalanceEntry.objects.filter(
        employee=target_user
    ).dates('entry_date', 'year', order='DESC')
    
    return render(request, 'leaves/balance_ledger.html', {
        'target_user': target_user,
        'entries': entries,
        'current_balance': current_balance,
        'current_year': year,
        'available_years': available_years,
        'carryover_days': target_user.carryover_leave_days,
        'current_year_days': target_user.current_year_leave_balance,
        'annual_entitlement': target_user.annual_leave_entitlement,
        'is_handler': request.user.is_leave_handler or request.user.is_administrator,
    })


@login_required
def manual_balance_adjustment(request, user_id):
    """
    Add a manual balance adjustment entry (handler/admin only).
    Description is mandatory for audit trail compliance.
    """
    target_user = get_object_or_404(User, pk=user_id)
    
    if not request.user.is_leave_handler and not request.user.is_administrator:
        raise PermissionDenied("Δεν έχετε δικαίωμα διόρθωσης υπολοίπου.")
    
    from leaves.utils.balance_ledger import get_last_balance
    last_balance = get_last_balance(target_user)
    suggested_balance = last_balance if last_balance is not None else target_user.current_regular_leave_balance
    
    if request.method == 'POST':
        entry_type = request.POST.get('entry_type', 'MANUAL_ADJUSTMENT')
        balance_after = request.POST.get('balance_after', '')
        days_delta = request.POST.get('days_delta', '')
        notes = request.POST.get('notes', '')
        description = request.POST.get('description', '').strip()
        
        if not notes:
            messages.error(request, 'Απαιτούνται σημειώσεις/αιτιολογία για την εγγραφή.')
            return render(request, 'leaves/manual_balance_adjustment.html', {
                'target_user': target_user,
                'suggested_balance': suggested_balance,
                'entry_types': RegularLeaveBalanceEntry.ENTRY_TYPES,
            })
        
        if not balance_after:
            messages.error(request, 'Απαιτείται η καταχώρηση του υπολοίπου μετά την πράξη.')
            return redirect('leaves:manual_balance_adjustment', user_id=user_id)
        
        try:
            balance_after = int(balance_after)
        except (ValueError, TypeError):
            messages.error(request, 'Το υπόλοιπο πρέπει να είναι ακέραιος αριθμός.')
            return redirect('leaves:manual_balance_adjustment', user_id=user_id)
        
        days_delta_val = None
        if days_delta:
            try:
                days_delta_val = int(days_delta)
            except (ValueError, TypeError):
                messages.error(request, 'Η μεταβολή πρέπει να είναι ακέραιος αριθμός.')
                return redirect('leaves:manual_balance_adjustment', user_id=user_id)
        
        create_balance_entry(
            employee=target_user,
            entry_type=entry_type,
            description=description,
            balance_after=balance_after,
            days_delta=days_delta_val,
            notes=notes,
            created_by=request.user
        )
        
        messages.success(request, f'Η εγγραφή δημιουργήθηκε επιτυχώς. Νέο υπόλοιπο: {balance_after}')
        return redirect('leaves:balance_ledger', user_id=user_id)
    
    return render(request, 'leaves/manual_balance_adjustment.html', {
        'target_user': target_user,
        'suggested_balance': suggested_balance,
        'entry_types': RegularLeaveBalanceEntry.ENTRY_TYPES,
    })