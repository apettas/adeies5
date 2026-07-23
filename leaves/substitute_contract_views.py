"""Views για συμβάσεις αναπληρωτών."""
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model

from leaves.models import SubstituteContract, SubstituteContractSettings
from leaves.utils.substitute_contracts import (
    activate_new_contract,
    default_contract_end_for_year,
    end_contract,
    end_contracts_bulk,
    get_active_contract,
    get_settings,
    resolve_opening_balance,
    substitute_users_qs,
    users_pending_contract,
    users_reappeared,
)

User = get_user_model()


def _require_handler(user):
    if not (user.is_leave_handler or user.is_administrator):
        raise PermissionDenied('Μόνο χειριστές αδειών έχουν πρόσβαση.')


def _parse_date(raw):
    if not raw:
        return None
    return datetime.strptime(raw, '%Y-%m-%d').date()


@login_required
def substitute_contracts_view(request):
    _require_handler(request.user)
    settings = get_settings()
    tab = request.GET.get('tab', 'ending')
    end_date = default_contract_end_for_year()

    ending_list = []
    if tab == 'ending':
        for u in substitute_users_qs(settings).filter(substitute_leave_status='ACTIVE'):
            c = get_active_contract(u)
            ending_list.append({'user': u, 'contract': c})

    pending = users_pending_contract(settings)
    reappeared = users_reappeared(settings)
    history = SubstituteContract.objects.select_related(
        'user', 'user__department', 'created_by', 'ended_by',
    ).order_by('-created_at')[:200]

    return render(request, 'leaves/substitute_contracts.html', {
        'settings': settings,
        'tab': tab,
        'ending_list': ending_list,
        'pending_list': pending,
        'reappeared_list': reappeared,
        'history_list': history,
        'default_end_date': end_date,
        'is_admin': request.user.is_administrator or request.user.is_superuser,
    })


@login_required
def substitute_contract_end_view(request, user_id):
    _require_handler(request.user)
    target = get_object_or_404(User, pk=user_id)
    contract = get_active_contract(target)

    if request.method == 'POST':
        notes = (request.POST.get('notes') or '').strip()
        end_date = _parse_date(request.POST.get('end_date'))
        try:
            end_contract(target, request.user, notes=notes, end_date=end_date)
            messages.success(request, f'Έληξε η σύμβαση του/της {target.full_name}.')
            return redirect('leaves:substitute_contracts')
        except ValueError as exc:
            messages.error(request, str(exc))

    return render(request, 'leaves/substitute_contract_end.html', {
        'target_user': target,
        'contract': contract,
        'default_end_date': default_contract_end_for_year(),
    })


@login_required
def substitute_contract_new_view(request, user_id):
    _require_handler(request.user)
    target = get_object_or_404(User, pk=user_id)
    settings = get_settings()
    today = datetime.now().date()
    suggested_end = default_contract_end_for_year(
        year=today.year if today.month <= settings.default_end_month else today.year + 1,
        settings=settings,
    )
    suggested_entitlement = target.annual_leave_entitlement or 0
    suggested_opening = resolve_opening_balance(suggested_entitlement, None, settings)

    if request.method == 'POST':
        notes = (request.POST.get('notes') or '').strip()
        try:
            start = _parse_date(request.POST.get('contract_start'))
            end = _parse_date(request.POST.get('contract_end'))
            entitled = int(request.POST.get('entitled_days', '0'))
            opening_raw = request.POST.get('opening_balance', '')
            opening = int(opening_raw) if opening_raw != '' else None
            if not start or not end:
                raise ValueError('Απαιτούνται ημερομηνίες έναρξης και λήξης.')
            if end < start:
                raise ValueError('Η λήξη πρέπει να είναι μετά την έναρξη.')
            activate_new_contract(
                user=target,
                contract_start=start,
                contract_end=end,
                entitled_days=entitled,
                notes=notes,
                created_by=request.user,
                opening_balance=opening,
            )
            messages.success(request, f'Καταχωρήθηκε νέα σύμβαση για {target.full_name}.')
            return redirect('leaves:substitute_contracts')
        except (TypeError, ValueError) as exc:
            messages.error(request, str(exc))

    return render(request, 'leaves/substitute_contract_new.html', {
        'target_user': target,
        'settings': settings,
        'suggested_start': today,
        'suggested_end': suggested_end,
        'suggested_entitlement': suggested_entitlement,
        'suggested_opening': suggested_opening,
    })


@login_required
@require_POST
def substitute_contracts_bulk_end(request):
    _require_handler(request.user)
    ids = request.POST.getlist('user_ids')
    notes = (request.POST.get('notes') or '').strip()
    end_date = _parse_date(request.POST.get('end_date'))
    if not ids:
        messages.error(request, 'Επιλέξτε τουλάχιστον έναν χρήστη.')
        return redirect('leaves:substitute_contracts')
    if not notes:
        messages.error(request, 'Απαιτείται σχόλιο για τη μαζική λήξη.')
        return redirect('leaves:substitute_contracts')
    ok, errors = end_contracts_bulk(ids, request.user, notes, end_date=end_date)
    if ok:
        messages.success(request, f'Έληξαν {ok} συμβάσεις.')
    for err in errors[:10]:
        messages.error(request, err)
    return redirect('leaves:substitute_contracts')


@login_required
@require_POST
def substitute_contracts_settings_save(request):
    if not (request.user.is_administrator or request.user.is_superuser):
        raise PermissionDenied('Μόνο διαχειριστές αλλάζουν ρυθμίσεις.')
    settings = SubstituteContractSettings.get_solo()
    try:
        settings.default_end_month = int(request.POST.get('default_end_month', settings.default_end_month))
        settings.default_end_day = int(request.POST.get('default_end_day', settings.default_end_day))
    except (TypeError, ValueError):
        messages.error(request, 'Μη έγκυρες αριθμητικές τιμές.')
        return redirect('leaves:substitute_contracts')
    settings.target_type_codes = request.POST.get('target_type_codes', settings.target_type_codes).strip()
    policy = request.POST.get('opening_balance_policy', settings.opening_balance_policy)
    if policy in dict(SubstituteContractSettings.OPENING_BALANCE_CHOICES):
        settings.opening_balance_policy = policy
    settings.end_user_message = request.POST.get('end_user_message', settings.end_user_message)
    settings.activate_user_message = request.POST.get(
        'activate_user_message', settings.activate_user_message,
    )
    settings.updated_by = request.user
    settings.save()
    messages.success(request, 'Οι ρυθμίσεις αποθηκεύτηκαν.')
    return redirect('leaves:substitute_contracts')
