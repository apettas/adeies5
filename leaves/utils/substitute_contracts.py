"""
Ροή συμβάσεων αναπληρωτών: λήξη, μηδενισμός, νέα σύμβαση, ειδοποιήσεις.
"""
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from accounts.role_constants import ROLE_LEAVE_HANDLER
from leaves.models import SubstituteContract, SubstituteContractSettings
from leaves.utils.balance_ledger import (
    change_entitlement,
    create_balance_entry,
    get_last_balance,
    get_last_buckets,
)


def get_settings():
    return SubstituteContractSettings.get_solo()


def target_codes(settings=None):
    settings = settings or get_settings()
    return settings.get_target_codes()


def substitute_users_qs(settings=None):
    codes = target_codes(settings)
    return User.objects.filter(
        is_active=True,
        registration_status='APPROVED',
        employee_type__code__in=codes,
    ).select_related('employee_type', 'department')


def default_contract_end_for_year(year=None, settings=None):
    settings = settings or get_settings()
    year = year or timezone.localdate().year
    day = min(settings.default_end_day, 28 if settings.default_end_month == 2 else 31)
    try:
        return date(year, settings.default_end_month, settings.default_end_day)
    except ValueError:
        return date(year, settings.default_end_month, day)


def resolve_opening_balance(entitled_days, opening_balance=None, settings=None):
    settings = settings or get_settings()
    if opening_balance is not None:
        return max(0, int(opening_balance))
    if settings.opening_balance_policy == 'zero':
        return 0
    if settings.opening_balance_policy == 'manual_only':
        return 0
    # entitlement (default)
    return max(0, int(entitled_days))


def get_active_contract(user):
    return (
        SubstituteContract.objects.filter(user=user, status='ACTIVE')
        .order_by('-contract_start', '-created_at')
        .first()
    )


@transaction.atomic
def end_contract(user, ended_by, notes='', end_date=None, notify_user=True):
    """
    Λήξη ενεργής σύμβασης: μηδενισμός υπολοίπου, PENDING_CONTRACT, ειδοποίηση.
    Αν δεν υπάρχει σύμβαση, εφαρμόζει μόνο μηδενισμό + status.
    """
    settings = get_settings()
    notes = (notes or '').strip()
    if not notes:
        raise ValueError('Απαιτείται σχόλιο/αιτιολογία για τη λήξη σύμβασης.')

    contract = get_active_contract(user)
    if contract:
        contract.status = 'ENDED'
        contract.ended_at = timezone.now()
        contract.ended_by = ended_by
        if end_date:
            contract.contract_end = end_date
        if notes:
            contract.notes = f'{contract.notes}\n{notes}'.strip() if contract.notes else notes
        contract.save()

    carry, current = get_last_buckets(user)
    total = carry + current
    if total > 0:
        create_balance_entry(
            employee=user,
            entry_type='CONTRACT_END_ZERO',
            description='Μηδενισμός υπολοίπου λόγω λήξης σύμβασης',
            days_delta=-total,
            notes=notes,
            created_by=ended_by,
            carryover_after=0,
            current_after=0,
        )
    elif get_last_balance(user) is None and (user.current_regular_leave_balance or 0) > 0:
        # Cache χωρίς ledger entry
        bal = user.current_regular_leave_balance
        create_balance_entry(
            employee=user,
            entry_type='CONTRACT_END_ZERO',
            description='Μηδενισμός υπολοίπου λόγω λήξης σύμβασης',
            days_delta=-bal,
            notes=notes,
            created_by=ended_by,
            carryover_after=0,
            current_after=0,
        )

    user.substitute_leave_status = 'PENDING_CONTRACT'
    user.substitute_reappearance_notified_at = None
    user.save(update_fields=['substitute_leave_status', 'substitute_reappearance_notified_at'])

    if notify_user:
        from notifications.utils import create_notification
        create_notification(
            user=user,
            title='Λήξη σύμβασης αναπληρωτή',
            message=settings.end_user_message,
            notification_type='warning',
            related_object=contract,
        )
    return contract


@transaction.atomic
def activate_new_contract(
    user,
    contract_start,
    contract_end,
    entitled_days,
    notes,
    created_by,
    opening_balance=None,
):
    """Νέα ACTIVE σύμβαση, δικαιούμενες, αρχικό υπόλοιπο, ACTIVE status."""
    settings = get_settings()
    notes = (notes or '').strip()
    if not notes:
        raise ValueError('Απαιτείται σχόλιο/αιτιολογία για τη νέα σύμβαση.')
    entitled_days = max(0, int(entitled_days))
    opening = resolve_opening_balance(entitled_days, opening_balance, settings)

    active = get_active_contract(user)
    if active:
        active.status = 'SUPERSEDED'
        active.ended_at = timezone.now()
        active.ended_by = created_by
        active.save(update_fields=['status', 'ended_at', 'ended_by'])

    # Αν είναι PENDING με υπόλοιπο, μηδενίζουμε πριν τη χορήγηση
    carry, current = get_last_buckets(user)
    leftover = carry + current
    if leftover > 0:
        create_balance_entry(
            employee=user,
            entry_type='CONTRACT_END_ZERO',
            description='Εκκαθάριση πριν από νέα σύμβαση',
            days_delta=-leftover,
            notes=notes,
            created_by=created_by,
            carryover_after=0,
            current_after=0,
        )

    contract = SubstituteContract.objects.create(
        user=user,
        contract_start=contract_start,
        contract_end=contract_end,
        entitled_days=entitled_days,
        opening_balance=opening,
        status='ACTIVE',
        notes=notes,
        created_by=created_by,
    )

    change_entitlement(user, entitled_days, notes, created_by)

    if opening > 0:
        create_balance_entry(
            employee=user,
            entry_type='CONTRACT_GRANT',
            description=f'Χορήγηση υπολοίπου νέας σύμβασης {contract_start}–{contract_end}',
            days_delta=opening,
            notes=notes,
            created_by=created_by,
            carryover_after=0,
            current_after=opening,
        )
    else:
        # Εγγύηση cache 0 με ρητούς κουβάδες αν δεν υπάρχει χορήγηση
        create_balance_entry(
            employee=user,
            entry_type='CONTRACT_GRANT',
            description=f'Ενεργοποίηση σύμβασης χωρίς αρχικό υπόλοιπο {contract_start}–{contract_end}',
            days_delta=0,
            notes=notes,
            created_by=created_by,
            carryover_after=0,
            current_after=0,
        )

    user.substitute_leave_status = 'ACTIVE'
    user.substitute_reappearance_notified_at = None
    user.save(update_fields=['substitute_leave_status', 'substitute_reappearance_notified_at'])

    from notifications.utils import create_notification
    create_notification(
        user=user,
        title='Νέα σύμβαση αναπληρωτή',
        message=settings.activate_user_message,
        notification_type='success',
        related_object=contract,
    )
    return contract


def end_contracts_bulk(user_ids, ended_by, notes, end_date=None):
    ok, errors = 0, []
    for uid in user_ids:
        try:
            user = User.objects.get(pk=uid)
            end_contract(user, ended_by, notes=notes, end_date=end_date)
            ok += 1
        except Exception as exc:
            errors.append(f'{uid}: {exc}')
    return ok, errors


def users_pending_contract(settings=None):
    return substitute_users_qs(settings).filter(
        substitute_leave_status__in=('PENDING_CONTRACT', 'ENDED_NO_REHIRE'),
    )


def users_with_active_contracts_ending_on_or_before(on_date, settings=None):
    settings = settings or get_settings()
    active_ids = SubstituteContract.objects.filter(
        status='ACTIVE',
        contract_end__lte=on_date,
        user__employee_type__code__in=target_codes(settings),
    ).values_list('user_id', flat=True)
    # Επίσης ACTIVE status χωρίς σύμβαση αλλά τύπος αναπληρωτή (χειροκίνητη ουρά)
    return User.objects.filter(
        Q(pk__in=active_ids) | Q(
            employee_type__code__in=target_codes(settings),
            substitute_leave_status='ACTIVE',
            substitute_contracts__isnull=True,
        )
    ).filter(is_active=True, registration_status='APPROVED').distinct().select_related(
        'employee_type', 'department',
    )


def users_reappeared(settings=None):
    """PENDING με πρόσφατο login notification flag ή γενικά pending."""
    return users_pending_contract(settings).filter(
        substitute_reappearance_notified_at__isnull=False,
    )


def maybe_notify_handlers_on_reappearance(user):
    """
    Στο login: αν PENDING_CONTRACT, ειδοποιεί χειριστές (anti-spam: 1×/ημέρα).
    """
    if not user.is_substitute_contract_blocked():
        return False
    if user.substitute_leave_status != 'PENDING_CONTRACT':
        return False

    now = timezone.now()
    last = user.substitute_reappearance_notified_at
    if last and (now - last) < timedelta(hours=20):
        return False

    from notifications.utils import create_notification
    handlers = User.objects.filter(
        is_active=True,
        roles__code=ROLE_LEAVE_HANDLER,
    ).distinct()
    title = 'Επανεμφάνιση αναπληρωτή'
    message = (
        f'Ο/Η {user.full_name} ({user.email}) έκανε είσοδο στην εφαρμογή '
        f'ενώ εκκρεμεί καταχώρηση νέας σύμβασης. '
        f'Μεταβείτε στην οθόνη «Συμβάσεις Αναπληρωτών».'
    )
    for handler in handlers:
        create_notification(
            user=handler,
            title=title,
            message=message,
            notification_type='warning',
            related_object=user,
        )
    user.substitute_reappearance_notified_at = now
    user.save(update_fields=['substitute_reappearance_notified_at'])
    return True
