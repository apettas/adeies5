"""Views για ετήσια ανανέωση κανονικών αδειών και αλλαγή δικαιούμενων."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.contrib.auth import get_user_model

from leaves.models import BalanceRenewalSettings
from leaves.utils.balance_ledger import change_entitlement, get_effective_entitlement
from leaves.utils.balance_renewal import (
    apply_renewal_season,
    get_or_open_season,
    is_apply_allowed,
    notify_users,
    refresh_season_statuses,
)

User = get_user_model()


def _require_handler(user):
    if not (user.is_leave_handler or user.is_administrator):
        raise PermissionDenied('Μόνο χειριστές αδειών έχουν πρόσβαση.')


@login_required
def change_entitlement_view(request, user_id):
    """Αλλαγή δικαιούμενων ημερών με υποχρεωτικό σχόλιο."""
    _require_handler(request.user)
    target_user = get_object_or_404(User, pk=user_id)

    if request.method == 'POST':
        notes = (request.POST.get('notes') or '').strip()
        raw = request.POST.get('new_entitlement', '')
        if not notes:
            messages.error(request, 'Απαιτείται σχόλιο/αιτιολογία.')
        else:
            try:
                new_val = int(raw)
                if new_val < 0:
                    raise ValueError
            except (TypeError, ValueError):
                messages.error(request, 'Οι δικαιούμενες ημέρες πρέπει να είναι μη αρνητικός ακέραιος.')
            else:
                change_entitlement(target_user, new_val, notes, request.user)
                messages.success(
                    request,
                    f'Οι δικαιούμενες ημέρες του/της {target_user.full_name} ενημερώθηκαν σε {new_val}.',
                )
                return redirect('leaves:balance_ledger', user_id=user_id)

    return render(request, 'leaves/change_entitlement.html', {
        'target_user': target_user,
        'current_entitlement': get_effective_entitlement(target_user),
    })


@login_required
def balance_renewal_view(request):
    """Κύρια οθόνη ετήσιας ανανέωσης (4 tabs)."""
    _require_handler(request.user)
    settings = BalanceRenewalSettings.get_solo()
    season = get_or_open_season()
    tab = request.GET.get('tab', 'expiring')

    statuses = season.user_statuses.select_related(
        'user', 'user__department', 'user__employee_type', 'notified_by',
    )

    expiring = statuses.filter(expiring_days__gt=0)
    unused_prior = statuses.filter(carryover_days__gt=0)
    preview = statuses.all()
    history = statuses.filter(
        Q(notified_at__isnull=False) | Q(applied_at__isnull=False)
    ).distinct()

    return render(request, 'leaves/balance_renewal.html', {
        'settings': settings,
        'season': season,
        'tab': tab,
        'expiring_list': expiring,
        'unused_prior_list': unused_prior,
        'preview_list': preview,
        'history_list': history,
        'apply_allowed': is_apply_allowed(closing_year=season.closing_year),
        'closing_year': season.closing_year,
        'new_year': season.new_year,
        'message_template': settings.user_message_template,
        'is_admin': request.user.is_administrator or request.user.is_superuser,
    })


@login_required
@require_POST
def balance_renewal_refresh(request):
    _require_handler(request.user)
    season = get_or_open_season()
    refresh_season_statuses(season)
    messages.success(request, 'Η λίστα ανανεώθηκε.')
    return redirect('leaves:balance_renewal')


@login_required
@require_POST
def balance_renewal_notify(request):
    _require_handler(request.user)
    season = get_or_open_season()
    ids = request.POST.getlist('user_ids')
    if not ids:
        messages.error(request, 'Επιλέξτε τουλάχιστον έναν χρήστη.')
        return redirect('leaves:balance_renewal')

    message_override = (request.POST.get('message') or '').strip() or None
    count = notify_users(season, ids, request.user, message_override=message_override)
    messages.success(request, f'Στάλθηκε ενημέρωση σε {count} χρήστες.')
    return redirect('leaves:balance_renewal')


@login_required
@require_POST
def balance_renewal_apply(request):
    _require_handler(request.user)
    season = get_or_open_season()
    force = request.POST.get('force') == '1' and (
        request.user.is_administrator or request.user.is_superuser
    )
    if not is_apply_allowed(closing_year=season.closing_year) and not force:
        messages.error(
            request,
            'Η εφαρμογή επιτρέπεται από την ημερομηνία εφαρμογής των ρυθμίσεων '
            '(ή με override διαχειριστή).',
        )
        return redirect('leaves:balance_renewal')

    skip_notify_check = request.POST.get('skip_notify_check') == '1'
    pending_notify = season.user_statuses.filter(
        expiring_days__gt=0, notified_at__isnull=True, applied_at__isnull=True,
    ).count()
    if pending_notify and not skip_notify_check and not force:
        messages.warning(
            request,
            f'Υπάρχουν {pending_notify} χρήστες με ημέρες προς λήξη χωρίς ενημέρωση. '
            'Στείλτε μηνύματα ή επιβεβαιώστε εφαρμογή χωρίς πλήρη ενημέρωση '
            '(checkbox στην καρτέλα προεπισκόπησης).',
        )
        return redirect('leaves:balance_renewal')

    ok, errors = apply_renewal_season(season, request.user, force=force)
    if ok:
        messages.success(request, f'Εφαρμόστηκε ανανέωση σε {ok} χρήστες.')
    for err in errors[:10]:
        messages.error(request, err)
    return redirect('leaves:balance_renewal')


@login_required
@require_POST
def balance_renewal_settings_save(request):
    if not (request.user.is_administrator or request.user.is_superuser):
        raise PermissionDenied('Μόνο διαχειριστές αλλάζουν ρυθμίσεις.')
    settings = BalanceRenewalSettings.get_solo()
    try:
        settings.warning_month = int(request.POST.get('warning_month', settings.warning_month))
        settings.warning_day = int(request.POST.get('warning_day', settings.warning_day))
        settings.apply_month = int(request.POST.get('apply_month', settings.apply_month))
        settings.apply_day = int(request.POST.get('apply_day', settings.apply_day))
        settings.reminder_interval_days = int(
            request.POST.get('reminder_interval_days', settings.reminder_interval_days)
        )
    except (TypeError, ValueError):
        messages.error(request, 'Μη έγκυρες αριθμητικές τιμές ρυθμίσεων.')
        return redirect('leaves:balance_renewal')

    settings.reminder_enabled = request.POST.get('reminder_enabled') == 'on'
    settings.target_type_codes = request.POST.get(
        'target_type_codes', settings.target_type_codes
    ).strip()
    settings.user_message_template = request.POST.get(
        'user_message_template', settings.user_message_template
    )
    settings.updated_by = request.user
    settings.save()
    messages.success(request, 'Οι ρυθμίσεις αποθηκεύτηκαν.')
    return redirect('leaves:balance_renewal')
