"""
Λογική ετήσιας ανανέωσης κανονικών αδειών (Φάση Α: Διοικητικοί / Εκπαιδευτικοί).
"""
from datetime import date

from django.db import transaction
from django.utils import timezone

from accounts.models import User
from accounts.role_constants import ROLE_LEAVE_HANDLER
from leaves.models import (
    BalanceRenewalSeason,
    BalanceRenewalSettings,
    BalanceRenewalUserStatus,
)
from leaves.utils.balance_ledger import (
    create_balance_entry,
    get_effective_entitlement,
    get_last_buckets,
)


def closing_year_for_date(today=None):
    """
    Έτος που κλείνει σχετικά με την προειδοποίηση.
    Από την ημερομηνία προειδοποίησης έως 31/12 → τρέχον έτος.
    Από 1/1 έως πριν την προειδοποίηση → προηγούμενο έτος.
    """
    today = today or timezone.localdate()
    settings = BalanceRenewalSettings.get_solo()
    today_md = (today.month, today.day)
    warning_md = (settings.warning_month, settings.warning_day)
    if today_md >= warning_md:
        return today.year
    return today.year - 1


def is_warning_period(today=None):
    today = today or timezone.localdate()
    settings = BalanceRenewalSettings.get_solo()
    today_md = (today.month, today.day)
    warning_md = (settings.warning_month, settings.warning_day)
    apply_md = (settings.apply_month, settings.apply_day)
    # Από warning έως τέλος έτους
    if today_md >= warning_md:
        return True
    # Από αρχή έτους έως (και χωρίς) apply — ακόμα σε παράθυρο προειδοποίησης
    if today_md < apply_md:
        return True
    return False


def is_apply_allowed(today=None, closing_year=None):
    """Εφαρμογή επιτρέπεται από την ημερομηνία εφαρμογής του νέου έτους και μετά."""
    today = today or timezone.localdate()
    settings = BalanceRenewalSettings.get_solo()
    cy = closing_year if closing_year is not None else closing_year_for_date(today)
    apply_date = date(cy + 1, settings.apply_month, min(settings.apply_day, 28))
    return today >= apply_date


def target_users_queryset(settings=None):
    settings = settings or BalanceRenewalSettings.get_solo()
    codes = settings.get_target_codes()
    return User.objects.filter(
        is_active=True,
        registration_status='APPROVED',
        employee_type__code__in=codes,
    ).select_related('employee_type', 'department')


def get_or_open_season(closing_year=None, opened_by=None):
    closing_year = closing_year or closing_year_for_date()
    season, _created = BalanceRenewalSeason.objects.get_or_create(closing_year=closing_year)
    just_opened = False
    if season.warning_opened_at is None:
        season.warning_opened_at = timezone.now()
        season.save(update_fields=['warning_opened_at'])
        just_opened = True
    refresh_season_statuses(season)
    if just_opened or season.handlers_notified_at is None:
        if is_warning_period():
            notify_handlers(season)
    return season


def refresh_season_statuses(season):
    """
    Ανανέωση snapshot ανά χρήστη.

    - expiring_days = υπάρχον μεταφερόμενο (carryover) → λήγει στην εφαρμογή
    - carryover_days = τρέχον υπόλοιπο έτους που κλείνει → θα μεταφερθεί
    - entitlement_days = νέο δικαίωμα
    """
    settings = BalanceRenewalSettings.get_solo()
    users = target_users_queryset(settings)
    for user in users:
        carry, current = get_last_buckets(user)
        entitlement = get_effective_entitlement(user)
        status, _ = BalanceRenewalUserStatus.objects.get_or_create(
            season=season,
            user=user,
            defaults={
                'expiring_days': carry,
                'carryover_days': current,
                'entitlement_days': entitlement,
            },
        )
        if status.applied_at:
            continue
        status.expiring_days = carry
        status.carryover_days = current
        status.entitlement_days = entitlement
        status.save(update_fields=['expiring_days', 'carryover_days', 'entitlement_days'])


def build_user_message(status, template=None):
    settings = BalanceRenewalSettings.get_solo()
    template = template or settings.user_message_template
    apply_date = f'{settings.apply_day:02d}/{settings.apply_month:02d}/{status.season.new_year}'
    return template.format(
        full_name=status.user.full_name,
        expiring_days=status.expiring_days,
        expiring_years=str(status.season.closing_year - 1),
        carryover_days=status.carryover_days,
        apply_date=apply_date,
    )


def notify_handlers(season):
    """Ειδοποίηση χειριστών ότι άνοιξε η περίοδος προειδοποίησης."""
    from notifications.utils import create_notification

    handlers = User.objects.filter(
        is_active=True,
        roles__code=ROLE_LEAVE_HANDLER,
    ).distinct()
    expiring_count = season.user_statuses.filter(expiring_days__gt=0).count()
    unused_count = season.user_statuses.filter(carryover_days__gt=0).count()
    title = f'Ετήσια ανανέωση αδειών {season.closing_year}→{season.new_year}'
    message = (
        f'Άνοιξε η περίοδος προειδοποίησης για την ετήσια ανανέωση κανονικών αδειών.\n'
        f'Χρήστες με ημέρες προς λήξη: {expiring_count}.\n'
        f'Χρήστες με υπόλοιπο προηγούμενου έτους προς μεταφορά: {unused_count}.\n'
        f'Μεταβείτε στην οθόνη «Ετήσια Ανανέωση» για έλεγχο και αποστολή μηνυμάτων.'
    )
    for handler in handlers:
        create_notification(
            user=handler,
            title=title,
            message=message,
            notification_type='warning',
            related_object=season,
        )
    season.handlers_notified_at = timezone.now()
    season.save(update_fields=['handlers_notified_at'])
    return handlers.count()


def notify_users(season, user_ids, sent_by, message_override=None):
    from notifications.utils import create_notification

    qs = BalanceRenewalUserStatus.objects.filter(
        season=season, user_id__in=user_ids,
    ).select_related('user', 'season')
    count = 0
    for status in qs:
        if status.expiring_days <= 0 and status.carryover_days <= 0:
            continue
        body = message_override or build_user_message(status)
        create_notification(
            user=status.user,
            title='Ενημέρωση ετήσιας ανανέωσης κανονικών αδειών',
            message=body,
            notification_type='info',
            related_object=season,
        )
        status.notified_at = timezone.now()
        status.notified_by = sent_by
        status.save(update_fields=['notified_at', 'notified_by'])
        count += 1
    return count


@transaction.atomic
def apply_renewal_for_user(status, applied_by):
    """
    1) Λήξη παλαιού carryover (expiring)
    2) Μεταφορά current → νέο carryover
    3) Χορήγηση entitlement στο current
    """
    user = status.user
    if status.applied_at:
        return status

    carry, current = get_last_buckets(user)
    entitlement = get_effective_entitlement(user)
    closing = status.season.closing_year
    new_year = status.season.new_year

    if carry > 0:
        create_balance_entry(
            employee=user,
            entry_type='CARRYOVER_EXPIRE',
            description=f'Λήξη υπολοίπου παλαιότερων ετών (πριν το {closing})',
            days_delta=-carry,
            notes=f'Ετήσια ανανέωση {closing}→{new_year}',
            created_by=applied_by,
            carryover_after=0,
            current_after=current,
        )
        carry, current = 0, current

    if current > 0:
        create_balance_entry(
            employee=user,
            entry_type='CARRYOVER_IMPORT',
            description=f'Μεταφορά υπολοίπου έτους {closing}',
            days_delta=0,
            notes=f'Ετήσια ανανέωση {closing}→{new_year}',
            created_by=applied_by,
            carryover_after=current,
            current_after=0,
        )
        carry, current = current, 0
    else:
        carry, current = 0, 0

    create_balance_entry(
        employee=user,
        entry_type='ANNUAL_GRANT',
        description=f'Χορήγηση δικαιώματος έτους {new_year}',
        days_delta=entitlement,
        notes=f'entitlement={entitlement}',
        created_by=applied_by,
        carryover_after=carry,
        current_after=entitlement,
    )

    status.applied_at = timezone.now()
    status.entitlement_days = entitlement
    status.apply_error = ''
    status.save(update_fields=['applied_at', 'entitlement_days', 'apply_error'])
    return status


def apply_renewal_season(season, applied_by, user_ids=None, force=False):
    if season.applied_at and not force and not user_ids:
        return 0, ['Η σεζόν έχει ήδη εφαρμοστεί.']

    qs = season.user_statuses.all()
    if user_ids:
        qs = qs.filter(user_id__in=user_ids)
    else:
        qs = qs.filter(applied_at__isnull=True)

    ok = 0
    errors = []
    for status in qs.select_related('user'):
        try:
            with transaction.atomic():
                apply_renewal_for_user(status, applied_by)
            ok += 1
        except Exception as exc:
            status.apply_error = str(exc)
            status.save(update_fields=['apply_error'])
            errors.append(f'{status.user}: {exc}')

    if not user_ids:
        season.applied_at = timezone.now()
        season.applied_by = applied_by
        season.save(update_fields=['applied_at', 'applied_by'])
    return ok, errors
