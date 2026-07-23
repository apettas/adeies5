"""
Utilities for regular leave balance ledger management.

Κουβάδες:
- carryover: μεταφερόμενο υπόλοιπο προηγούμενου έτους
- current: υπόλοιπο τρέχοντος δικαιώματος
Αφαίρεση άδειας: FIFO — πρώτα carryover, μετά current.
"""
from django.utils import timezone
from leaves.models import RegularLeaveBalanceEntry


def get_effective_entitlement(user):
    """Τρέχουσες δικαιούμενες ημέρες με fallback ανά τύπο υπαλλήλου."""
    entitlement = user.annual_leave_entitlement
    if entitlement and entitlement > 0:
        return entitlement
    code = getattr(getattr(user, 'employee_type', None), 'code', None)
    if code == 'EDUCATIONAL':
        return 10
    return 25


def get_last_entry(employee):
    return RegularLeaveBalanceEntry.objects.filter(
        employee=employee
    ).order_by('-entry_date', '-created_at').first()


def get_last_balance(employee):
    """Τελευταίο balance_after ή None."""
    last_entry = get_last_entry(employee)
    if last_entry:
        return last_entry.balance_after
    return None


def get_last_buckets(employee):
    """
    Επιστρέφει (carryover, current).
    Για παλιές εγγραφές χωρίς κουβάδες: όλο το υπόλοιπο θεωρείται current.
    """
    last_entry = get_last_entry(employee)
    if not last_entry:
        total = employee.current_regular_leave_balance or 0
        return 0, total
    if last_entry.carryover_after is not None and last_entry.current_after is not None:
        return max(0, last_entry.carryover_after), max(0, last_entry.current_after)
    total = last_entry.balance_after or 0
    return 0, max(0, total)


def apply_fifo_deduction(carryover, current, days):
    """Αφαίρεση ημερών: πρώτα από carryover, μετά από current."""
    days = max(0, int(days))
    from_carry = min(carryover, days)
    remaining = days - from_carry
    from_current = min(current, remaining)
    new_carry = carryover - from_carry
    new_current = current - from_current
    return new_carry, new_current, from_carry, from_current


def resolve_buckets_for_entry(employee, balance_after=None, days_delta=None,
                              carryover_after=None, current_after=None):
    """Υπολογισμός κουβάδων για νέα εγγραφή."""
    prev_carry, prev_current = get_last_buckets(employee)
    prev_total = prev_carry + prev_current

    if carryover_after is not None and current_after is not None:
        return max(0, carryover_after), max(0, current_after)

    if days_delta is not None and days_delta < 0:
        return apply_fifo_deduction(prev_carry, prev_current, -days_delta)[:2]

    if days_delta is not None and days_delta > 0:
        return prev_carry, prev_current + days_delta

    if balance_after is not None:
        target = max(0, int(balance_after))
        if target == prev_total:
            return prev_carry, prev_current
        if target < prev_total:
            return apply_fifo_deduction(prev_carry, prev_current, prev_total - target)[:2]
        # αύξηση: πάει στο current
        return prev_carry, prev_current + (target - prev_total)

    return prev_carry, prev_current


def create_balance_entry(employee, entry_type, description, balance_after=None,
                        leave_request=None, days_delta=None, notes='', created_by=None,
                        balance_before=None, carryover_after=None, current_after=None,
                        old_entitlement=None, new_entitlement=None, entry_date=None):
    """
    Δημιουργία εγγραφής ledger και ενημέρωση cache.
    Αν δοθούν carryover_after/current_after χρησιμοποιούνται ως έχουν.
    Αλλιώς υπολογίζονται από days_delta (FIFO) ή balance_after.
    """
    prev_carry, prev_current = get_last_buckets(employee)
    if balance_before is None:
        last = get_last_balance(employee)
        balance_before = last if last is not None else (employee.current_regular_leave_balance or 0)

    new_carry, new_current = resolve_buckets_for_entry(
        employee,
        balance_after=balance_after,
        days_delta=days_delta,
        carryover_after=carryover_after,
        current_after=current_after,
    )
    computed_after = new_carry + new_current
    if balance_after is None:
        balance_after = computed_after
    else:
        # Συγχρονισμός: προτεραιότητα στα ρητά buckets αν δόθηκαν
        if carryover_after is None and current_after is None and balance_after != computed_after:
            new_carry, new_current = resolve_buckets_for_entry(
                employee, balance_after=balance_after, days_delta=None,
            )
            balance_after = new_carry + new_current

    if days_delta is None and entry_type != 'ENTITLEMENT_CHANGE':
        days_delta = balance_after - balance_before

    entry = RegularLeaveBalanceEntry.objects.create(
        employee=employee,
        entry_type=entry_type,
        entry_date=entry_date or timezone.now().date(),
        description=description,
        balance_before=balance_before,
        balance_after=balance_after,
        carryover_after=new_carry,
        current_after=new_current,
        leave_request=leave_request,
        days_delta=days_delta,
        notes=notes,
        created_by=created_by,
        old_entitlement=old_entitlement,
        new_entitlement=new_entitlement,
    )

    if entry_type != 'ENTITLEMENT_CHANGE':
        employee.current_regular_leave_balance = balance_after
        employee.save(update_fields=['current_regular_leave_balance'])

    return entry


def change_entitlement(employee, new_entitlement, notes, created_by):
    """Αλλαγή δικαιούμενων χωρίς αυτόματη μεταβολή υπολοίπου."""
    old = employee.annual_leave_entitlement or 0
    new_entitlement = int(new_entitlement)
    carry, current = get_last_buckets(employee)
    total = carry + current
    entry = create_balance_entry(
        employee=employee,
        entry_type='ENTITLEMENT_CHANGE',
        description=f'Δικαιούμενες: {old} → {new_entitlement}',
        balance_after=total,
        days_delta=0,
        notes=notes,
        created_by=created_by,
        carryover_after=carry,
        current_after=current,
        old_entitlement=old,
        new_entitlement=new_entitlement,
    )
    employee.annual_leave_entitlement = new_entitlement
    employee.save(update_fields=['annual_leave_entitlement'])
    return entry


def get_balance_entries(employee, year=None):
    qs = RegularLeaveBalanceEntry.objects.filter(employee=employee)
    if year:
        qs = qs.filter(entry_date__year=year)
    return qs.order_by('-entry_date', '-created_at')


def get_carryover_days(employee):
    """Μεταφερόμενο υπόλοιπο από τον τελευταίο κουβά."""
    carry, _current = get_last_buckets(employee)
    return carry


def get_leave_balance_breakdown(user):
    """Αναλυτικό υπόλοιπο από κουβάδες ledger."""
    carryover, current = get_last_buckets(user)
    return {
        'carryover_days': carryover,
        'current_year_days': current,
        'total_days': carryover + current,
        'annual_entitlement': get_effective_entitlement(user),
    }


def deduct_leave_days(employee, days_used, leave_request=None, created_by=None,
                      description=None, notes='', balance_after=None):
    """
    Αφαίρεση ημερών κανονικής με FIFO.
    Αν δοθεί balance_after από handler, τηρείται το σύνολο με FIFO στην αφαίρεση.
    """
    days_used = max(0, int(days_used))
    prev_carry, prev_current = get_last_buckets(employee)
    prev_total = prev_carry + prev_current

    if balance_after is not None:
        target = max(0, int(balance_after))
        deduction = max(0, prev_total - target)
        credit = max(0, target - prev_total)
        if deduction:
            new_carry, new_current, from_c, from_cur = apply_fifo_deduction(
                prev_carry, prev_current, deduction,
            )
            notes_extra = f'FIFO: μεταφερόμενο -{from_c}, τρέχον -{from_cur}'
        else:
            new_carry, new_current = prev_carry, prev_current + credit
            notes_extra = f'Πίστωση τρέχοντος +{credit}' if credit else ''
        full_notes = notes
        if notes_extra:
            full_notes = f'{notes}\n{notes_extra}'.strip()
        return create_balance_entry(
            employee=employee,
            entry_type='LEAVE_GRANTED',
            description=description or 'Ολοκλήρωση κανονικής άδειας',
            balance_after=new_carry + new_current,
            leave_request=leave_request,
            days_delta=(new_carry + new_current) - prev_total,
            notes=full_notes,
            created_by=created_by,
            carryover_after=new_carry,
            current_after=new_current,
        )

    new_carry, new_current, from_c, from_cur = apply_fifo_deduction(
        prev_carry, prev_current, days_used,
    )
    full_notes = notes
    fifo_note = f'FIFO: μεταφερόμενο -{from_c}, τρέχον -{from_cur}'
    full_notes = f'{notes}\n{fifo_note}'.strip() if notes else fifo_note
    return create_balance_entry(
        employee=employee,
        entry_type='LEAVE_GRANTED',
        description=description or 'Ολοκλήρωση κανονικής άδειας',
        leave_request=leave_request,
        days_delta=-days_used,
        notes=full_notes,
        created_by=created_by,
        carryover_after=new_carry,
        current_after=new_current,
    )


def credit_revoked_leave_days(employee, days, leave_request=None, created_by=None,
                              description=None, notes=''):
    """
    Πίστωση ημερών λόγω ανάκλησης άδειας (LEAVE_REVOKED).
    Οι ημέρες προστίθενται στον κουβά τρέχοντος δικαιώματος.
    """
    days = max(0, int(days))
    if days <= 0:
        return None

    prev_carry, prev_current = get_last_buckets(employee)
    new_carry = prev_carry
    new_current = prev_current + days
    full_notes = notes
    credit_note = f'Πίστωση τρέχοντος +{days}'
    full_notes = f'{notes}\n{credit_note}'.strip() if notes else credit_note

    return create_balance_entry(
        employee=employee,
        entry_type='LEAVE_REVOKED',
        description=description or 'Ανάκληση κανονικής άδειας',
        leave_request=leave_request,
        days_delta=days,
        notes=full_notes,
        created_by=created_by,
        carryover_after=new_carry,
        current_after=new_current,
    )
