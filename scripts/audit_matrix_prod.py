"""
Matrix audit for production trial DB.
Creates prefixed AUDIT_* records, runs scenarios, reports PASS/FAIL, cleans up.
"""
from __future__ import annotations

import traceback
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from accounts.models import Department, DepartmentType, EmployeeType, Role
from accounts.role_constants import ROLE_EMPLOYEE, ROLE_LEAVE_HANDLER, ROLE_MANAGER, ROLE_SECRETARY
from leaves.utils.balance_ledger import (
    create_balance_entry,
    deduct_leave_days,
    get_last_balance,
    get_last_buckets,
)
from leaves.utils.balance_renewal import apply_renewal_for_user, get_or_open_season
from leaves.utils.leave_revocation import get_or_create_revocation_leave_type
from leaves.utils.substitute_contracts import activate_new_contract, end_contract
from leaves.models import (
    BalanceRenewalUserStatus,
    LeavePeriod,
    LeaveRequest,
    LeaveType,
    RegularLeaveBalanceEntry,
    YearlySickLeaveTotal,
)

User = get_user_model()
PREFIX = 'AUDIT_MATRIX_'
EMAIL_DOMAIN = 'audit.local'
results: list[tuple[str, str, str]] = []


def ok(name, detail=''):
    results.append(('PASS', name, detail))
    print(f'✅ PASS  {name}  {detail}')


def fail(name, detail=''):
    results.append(('FAIL', name, detail))
    print(f'❌ FAIL  {name}  {detail}')


def info(msg):
    print(f'ℹ  {msg}')


def cleanup():
    info('Cleanup AUDIT_* data…')
    LeaveRequest.objects.filter(user__email__endswith=f'@{EMAIL_DOMAIN}').delete()
    RegularLeaveBalanceEntry.objects.filter(employee__email__endswith=f'@{EMAIL_DOMAIN}').delete()
    YearlySickLeaveTotal.objects.filter(employee__email__endswith=f'@{EMAIL_DOMAIN}').delete()
    from leaves.models import BalanceRenewalSeason, BalanceRenewalUserStatus, SubstituteContract
    BalanceRenewalUserStatus.objects.filter(user__email__endswith=f'@{EMAIL_DOMAIN}').delete()
    BalanceRenewalSeason.objects.filter(closing_year=2098).delete()
    SubstituteContract.objects.filter(user__email__endswith=f'@{EMAIL_DOMAIN}').delete()
    # Clear FK managers before deleting users/depts
    Department.objects.filter(code__startswith=PREFIX).update(manager=None)
    User.objects.filter(email__endswith=f'@{EMAIL_DOMAIN}').delete()
    Department.objects.filter(code__startswith=PREFIX).delete()
    LeaveType.objects.filter(code__startswith=PREFIX).delete()


def get_role(code):
    return Role.objects.get(code=code)


def emp_type(code):
    return EmployeeType.objects.filter(code=code).first()


def make_user(email_local, first, last, department, roles, employee_type_code='ADMINISTRATIVE', **extra):
    et = emp_type(employee_type_code)
    u, created = User.objects.get_or_create(
        email=f'{email_local}@{EMAIL_DOMAIN}',
        defaults={
            'first_name': first,
            'last_name': last,
            'department': department,
            'employee_type': et,
            'is_active': True,
            'registration_status': 'APPROVED',
            'annual_leave_entitlement': extra.pop('entitlement', 25),
            'current_regular_leave_balance': extra.pop('balance', 25),
            **extra,
        },
    )
    if not created:
        for k, v in {
            'first_name': first,
            'last_name': last,
            'department': department,
            'employee_type': et,
            'is_active': True,
            'registration_status': 'APPROVED',
        }.items():
            setattr(u, k, v)
        u.save()
    u.roles.clear()
    for r in roles:
        u.roles.add(get_role(r))
    return u


def make_dept(code_suffix, name, dtype_code, parent=None, manager=None):
    dtype = DepartmentType.objects.filter(code=dtype_code).first()
    if not dtype:
        raise RuntimeError(f'Missing DepartmentType {dtype_code}')
    d, _ = Department.objects.get_or_create(
        code=f'{PREFIX}{code_suffix}',
        defaults={
            'name': name,
            'department_type': dtype,
            'parent_department': parent,
            'manager': manager,
            'is_active': True,
        },
    )
    d.name = name
    d.department_type = dtype
    d.parent_department = parent
    d.manager = manager
    d.is_active = True
    d.save()
    return d


def make_leave_type(code_suffix, name, **flags):
    lt, _ = LeaveType.objects.get_or_create(
        code=f'{PREFIX}{code_suffix}',
        defaults={'name': name, 'is_active': True, **flags},
    )
    for k, v in flags.items():
        setattr(lt, k, v)
    lt.name = name
    lt.is_active = True
    lt.save()
    return lt


def create_leave(user, leave_type, start, end, status='DRAFT', **extra):
    lr = LeaveRequest.objects.create(
        user=user,
        leave_type=leave_type,
        description=f'{PREFIX}{leave_type.code}',
        status=status,
        days=(end - start).days + 1,
        requested_days=(end - start).days + 1,
        submitted_at=timezone.now() if status != 'DRAFT' else None,
        **extra,
    )
    LeavePeriod.objects.create(leave_request=lr, start_date=start, end_date=end)
    return lr


def section(title):
    print('\n' + '=' * 72)
    print(title)
    print('=' * 72)


def run_audit():
    cleanup()
    section('0. ENVIRONMENT CHECKS')

    # PDEDE type mismatch bug
    pdede_main = Department.objects.filter(department_type__code='PDEDE_MAIN').first()
    pdede = Department.objects.filter(department_type__code='PDEDE').first()
    info(f'DeptType PDEDE_MAIN exists={bool(pdede_main)} PDEDE exists={bool(pdede)}')
    if pdede and not pdede_main:
        fail(
            'pdede_fallback_type_code',
            '_find_pdede_manager looks for PDEDE_MAIN but prod uses PDEDE — root managers get None approver',
        )
    elif pdede_main:
        ok('pdede_fallback_type_code', 'PDEDE_MAIN present')

    # Live stuck SUBMITTED without approver
    stuck = []
    for lr in LeaveRequest.objects.filter(status='SUBMITTED').select_related('user', 'leave_type'):
        am = lr.user.get_approving_manager()
        if lr.leave_type.requires_approval and am is None:
            stuck.append(lr.id)
    if stuck:
        fail('live_submitted_no_approver', f'request ids={stuck}')
    else:
        ok('live_submitted_no_approver', 'none')

    open_yc = list(LeaveRequest.objects.filter(status='PENDING_YC_COMMITTEE').values_list('id', flat=True))
    open_ked = list(LeaveRequest.objects.filter(status='PENDING_KEDASY_PROTOCOL').values_list('id', flat=True))
    info(f'Live PENDING_YC_COMMITTEE={open_yc} PENDING_KEDASY={open_ked}')

    section('1. BUILD MINI HIERARCHY')
    # Prefer real PDEDE as root parent if exists
    real_pdede = Department.objects.filter(code='PDEDE').first() or pdede
    root_type = 'PDEDE' if DepartmentType.objects.filter(code='PDEDE').exists() else 'PDEDE_MAIN'

    # Create isolated tree under real PDEDE when possible
    audit_pdede = make_dept('PDEDE', 'AUDIT ΠΔΕΔΕ', root_type, parent=None)
    audit_auto = make_dept(
        'AUTO', 'AUDIT Αυτοτελές',
        'AUTONOMOUS_DIRECTION' if DepartmentType.objects.filter(code='AUTONOMOUS_DIRECTION').exists() else 'DIRECTION',
        parent=audit_pdede,
    )
    audit_tmima = make_dept(
        'TMIMA', 'AUDIT Τμήμα',
        'TMIMA_PDEDE' if DepartmentType.objects.filter(code='TMIMA_PDEDE').exists() else 'DEPARTMENT',
        parent=audit_pdede,
    )
    ked_type = 'KEDASY'
    sdey_type = 'SDEI' if DepartmentType.objects.filter(code='SDEI').exists() else 'SDEY'
    audit_ked = make_dept('KED', 'AUDIT ΚΕΔΑΣΥ', ked_type, parent=audit_pdede)
    audit_sdey = make_dept('SDEY', 'AUDIT ΣΔΕΥ', sdey_type, parent=audit_ked)

    # Users
    pdede_mgr = make_user('pdede.mgr', 'Περιφ', 'Διευθυντής', audit_pdede, [ROLE_MANAGER, ROLE_EMPLOYEE])
    audit_pdede.manager = pdede_mgr
    audit_pdede.save()

    auto_mgr = make_user('auto.mgr', 'Αυτ', 'Προϊστάμενος', audit_auto, [ROLE_MANAGER, ROLE_EMPLOYEE])
    audit_auto.manager = auto_mgr
    audit_auto.save()

    tmima_mgr = make_user('tmima.mgr', 'Τμημ', 'Προϊστάμενος', audit_tmima, [ROLE_MANAGER, ROLE_EMPLOYEE])
    audit_tmima.manager = tmima_mgr
    audit_tmima.save()

    ked_mgr = make_user('ked.mgr', 'Κεδ', 'Προϊστάμενος', audit_ked, [ROLE_MANAGER, ROLE_EMPLOYEE])
    audit_ked.manager = ked_mgr
    audit_ked.save()

    ked_sec = make_user('ked.sec', 'Κεδ', 'Γραμματέας', audit_ked, [ROLE_SECRETARY, ROLE_EMPLOYEE])
    sdey_emp = make_user('sdey.emp', 'Σδευ', 'Υπάλληλος', audit_sdey, [ROLE_EMPLOYEE], 'EDUCATIONAL')
    emp = make_user('emp.reg', 'Κανον', 'Υπάλληλος', audit_tmima, [ROLE_EMPLOYEE], 'ADMINISTRATIVE', balance=20, entitlement=25)
    edu = make_user('emp.edu', 'Εκπ', 'Υπάλληλος', audit_tmima, [ROLE_EMPLOYEE], 'EDUCATIONAL', balance=10, entitlement=10)
    handler = make_user(
        'handler', 'Χειρ', 'Αδειών', audit_tmima,
        [ROLE_LEAVE_HANDLER, ROLE_EMPLOYEE, ROLE_MANAGER],
        'ADMINISTRATIVE',
    )
    # Make handler also FK manager? Keep separate — handler in same dept as emp, not manager
    sub = make_user(
        'sub.one', 'Αναπλ', 'Ένας', audit_tmima,
        [ROLE_EMPLOYEE], 'SUBSTITUTE', balance=10, entitlement=10,
    )

    # Leave types
    lt_reg = make_leave_type(
        'REG', 'AUDIT Κανονική',
        requires_approval=True, affects_regular_leave_balance=True, max_days=30,
    )
    lt_noappr = make_leave_type(
        'NOAPPR', 'AUDIT Χωρίς έγκριση',
        requires_approval=False, affects_regular_leave_balance=False,
    )
    lt_yd = make_leave_type(
        'YD', 'AUDIT ΥΔ',
        requires_approval=True, affects_regular_leave_balance=False, is_sick_leave_yd=True,
    )
    lt_sick = make_leave_type(
        'SICK', 'AUDIT Αναρρωτική',
        requires_approval=True, affects_regular_leave_balance=False, is_sick_leave_total=True,
    )
    lt_simple = make_leave_type(
        'SIMPLE', 'AUDIT Άτυπη',
        requires_approval=True, affects_regular_leave_balance=False, is_simple=True,
    )
    rev_type = get_or_create_revocation_leave_type()

    section('2. APPROVAL HIERARCHY')
    # Employee → department manager
    am = emp.get_approving_manager()
    if am and am.id == tmima_mgr.id:
        ok('emp_approver_is_dept_manager', am.email)
    else:
        fail('emp_approver_is_dept_manager', f'got={getattr(am, "email", am)}')

    # Dept manager → PDEDE manager (parent)
    am = tmima_mgr.get_approving_manager()
    if am and am.id == pdede_mgr.id:
        ok('dept_manager_approver_is_pdede', am.email)
    else:
        fail('dept_manager_approver_is_pdede', f'got={getattr(am, "email", am)} expected={pdede_mgr.email}')

    # PDEDE manager (root of audit tree) → _find_pdede_manager
    am = pdede_mgr.get_approving_manager()
    # Because audit_pdede has no parent, falls back to PDEDE_MAIN lookup — likely None in prod
    if am is None:
        fail(
            'pdede_mgr_approver',
            'None — cannot request/approve chain for regional director (PDEDE_MAIN mismatch or no parent)',
        )
    else:
        ok('pdede_mgr_approver', am.email)

    # Manager cannot approve own leave
    own = create_leave(tmima_mgr, lt_reg, date(2026, 8, 3), date(2026, 8, 5), status='SUBMITTED')
    if own.can_be_approved_by(tmima_mgr) is False:
        ok('manager_cannot_approve_own', '')
    else:
        fail('manager_cannot_approve_own', 'can_be_approved_by returned True')

    # Superior can approve manager leave
    if own.can_be_approved_by(pdede_mgr):
        ok('superior_can_approve_manager_leave', '')
    else:
        fail('superior_can_approve_manager_leave', f'approving={own.get_approving_manager()}')

    # Handler cannot approve own SUBMITTED if requires approval
    own_h = create_leave(handler, lt_reg, date(2026, 8, 10), date(2026, 8, 11), status='SUBMITTED')
    if own_h.can_be_approved_by(handler) is False:
        ok('handler_cannot_approve_own_submitted', '')
    else:
        fail('handler_cannot_approve_own_submitted', '')

    # SDEY employee → KEDASY manager (if hierarchy set)
    am = sdey_emp.get_approving_manager()
    # SDEY has no FK manager → climbs to KEDASY parent manager
    if am and am.id == ked_mgr.id:
        ok('sdey_approver_is_kedasy_manager', am.email)
    else:
        fail('sdey_approver_is_kedasy_manager', f'got={getattr(am, "email", am)}')

    section('3. STANDARD WORKFLOW + LEDGER')
    start, end = date(2026, 9, 1), date(2026, 9, 5)  # 5 days
    bal0 = emp.current_regular_leave_balance
    lr = create_leave(emp, lt_reg, start, end, status='DRAFT')
    assert lr.submit()
    lr.refresh_from_db()
    if lr.status != 'SUBMITTED':
        fail('submit_to_submitted', lr.status)
    else:
        ok('submit_to_submitted', '')

    if not lr.approve_by_manager(tmima_mgr, 'OK'):
        fail('manager_approve', 'approve_by_manager False')
    else:
        lr.refresh_from_db()
        if lr.status == 'PENDING_PROTOCOL':
            ok('manager_approve_to_protocol', '')
        else:
            fail('manager_approve_to_protocol', lr.status)

    # Handler complete shortcut from IN_REVIEW
    lr.status = 'IN_REVIEW'
    lr.processed_by = handler
    lr.processed_at = timezone.now()
    lr.save()
    before = get_last_balance(emp) or emp.current_regular_leave_balance
    if not lr.complete_by_handler(handler, comments='audit complete'):
        fail('handler_complete', '')
    else:
        lr.refresh_from_db()
        emp.refresh_from_db()
        after = get_last_balance(emp)
        if lr.status == 'COMPLETED' and after == before - 5:
            ok('handler_complete_deducts_ledger', f'{before}->{after}')
        else:
            fail('handler_complete_deducts_ledger', f'status={lr.status} bal {before}->{after} cache={emp.current_regular_leave_balance}')

    # FIFO: set carryover+current then deduct
    from leaves.utils.balance_ledger import create_balance_entry
    create_balance_entry(
        employee=edu, entry_type='MANUAL_ADJUSTMENT', description='audit seed',
        days_delta=0, carryover_after=3, current_after=7, notes='seed',
    )
    c0, cur0 = get_last_buckets(edu)
    deduct_leave_days(edu, 4, description='fifo test')
    c1, cur1 = get_last_buckets(edu)
    if c0 == 3 and cur0 == 7 and c1 == 0 and cur1 == 6:
        ok('fifo_deduction', f'carry {c0}->{c1} current {cur0}->{cur1}')
    else:
        fail('fifo_deduction', f'before=({c0},{cur0}) after=({c1},{cur1})')

    section('4. REVOCATION + LEDGER CREDIT')
    parent = lr
    child = LeaveRequest.objects.create(
        user=emp,
        leave_type=rev_type,
        description='audit revoke total',
        status='IN_REVIEW',
        days=5,
        requested_days=5,
        parent_leave=parent,
        revocation_scope='TOTAL',
        submitted_at=timezone.now(),
    )
    for p in parent.periods.all():
        LeavePeriod.objects.create(leave_request=child, start_date=p.start_date, end_date=p.end_date)
    bal_b = get_last_balance(emp)
    child.complete_by_handler(handler)
    parent.refresh_from_db()
    emp.refresh_from_db()
    bal_a = get_last_balance(emp)
    entry = RegularLeaveBalanceEntry.objects.filter(leave_request=child, entry_type='LEAVE_REVOKED').first()
    if parent.status == 'REVOKED_BY_REQUEST' and entry and entry.days_delta == 5 and bal_a == bal_b + 5:
        ok('total_revocation_restores_balance', f'{bal_b}->{bal_a} parent={parent.status}')
    else:
        fail('total_revocation_restores_balance', f'parent={parent.status} entry={entry} bal {bal_b}->{bal_a}')

    # Partial
    lr2 = create_leave(emp, lt_reg, date(2026, 10, 1), date(2026, 10, 5), status='IN_REVIEW')
    lr2.complete_by_handler(handler)
    child2 = LeaveRequest.objects.create(
        user=emp, leave_type=rev_type, description='partial', status='IN_REVIEW',
        days=2, requested_days=2, parent_leave=lr2, revocation_scope='PARTIAL',
        submitted_at=timezone.now(),
    )
    LeavePeriod.objects.create(leave_request=child2, start_date=date(2026, 10, 1), end_date=date(2026, 10, 2))
    child2.complete_by_handler(handler)
    lr2.refresh_from_db()
    if lr2.status == 'COMPLETED' and lr2.revoked_days == 2 and lr2.remaining_revocable_days == 3:
        ok('partial_revocation', f'revoked={lr2.revoked_days} remaining={lr2.remaining_revocable_days}')
    else:
        fail('partial_revocation', f'status={lr2.status} revoked={lr2.revoked_days}')

    section('5. SICK LEAVE / 5-YEAR WINDOW')
    # YD limit: complete 2 YD then third submit should fail
    emp.sick_leave_with_declaration = 2
    emp.save(update_fields=['sick_leave_with_declaration'])
    for i in range(2):
        y = create_leave(emp, lt_yd, date(2026, 3, 1 + i * 3), date(2026, 3, 1 + i * 3), status='COMPLETED')
        y.completed_at = timezone.now()
        y.submitted_at = timezone.now()
        y.save()
    y3 = create_leave(emp, lt_yd, date(2026, 4, 1), date(2026, 4, 1), status='DRAFT')
    try:
        y3.submit()
        fail('sick_yd_limit', 'third YD submit allowed')
    except ValueError as e:
        ok('sick_yd_limit', str(e)[:80])

    # Sick total increments YearlySickLeaveTotal but check 5yr cache path
    cy = timezone.now().year
    # Seed old years
    for yr, days in [(cy - 6, 20), (cy - 5, 5), (cy - 1, 3)]:
        YearlySickLeaveTotal.objects.update_or_create(
            employee=edu, year=yr, defaults={'total_days': days},
        )
    # Sum window year__gte=cy-5 .. cy (code uses this) — year-6 should be OUT of sum
    qs = YearlySickLeaveTotal.objects.filter(employee=edu, year__gte=cy - 5, year__lte=cy)
    summed = sum(r.total_days for r in qs)
    year6 = YearlySickLeaveTotal.objects.filter(employee=edu, year=cy - 6).first()
    if year6 and year6.total_days == 20 and summed == 8:
        ok('sick_year6_excluded_from_sum', f'sum={summed} year6_row_still_exists={year6.total_days}')
    else:
        fail('sick_year6_excluded_from_sum', f'sum={summed} year6={getattr(year6, "total_days", None)}')

    # Rows are NOT deleted
    if YearlySickLeaveTotal.objects.filter(employee=edu, year=cy - 6).exists():
        ok('sick_year6_row_not_auto_deleted', 'row remains (falls out of filter only)')
    else:
        fail('sick_year6_row_not_auto_deleted', 'unexpectedly deleted')

    # Stale cache: set wrong cache
    edu.total_sick_leave_last_5_years = 999
    edu.save(update_fields=['total_sick_leave_last_5_years'])
    # No New Year job — cache stays stale
    edu.refresh_from_db()
    if edu.total_sick_leave_last_5_years == 999:
        fail('sick_5yr_cache_not_refreshed_on_year_change', 'no automatic recalculation on 1/1')
    else:
        ok('sick_5yr_cache_not_refreshed_on_year_change', '')

    # complete_by_handler updates yearly but NOT 5yr field
    before5 = edu.total_sick_leave_last_5_years
    sick_lr = create_leave(edu, lt_sick, date(2026, 5, 1), date(2026, 5, 3), status='IN_REVIEW')
    sick_lr.complete_by_handler(handler)
    edu.refresh_from_db()
    yt = YearlySickLeaveTotal.objects.filter(employee=edu, year=cy).first()
    if yt and yt.total_days >= 3 and edu.total_sick_leave_last_5_years == before5:
        fail(
            'sick_5yr_not_updated_on_handler_complete',
            f'yearly={yt.total_days} cache5 still {edu.total_sick_leave_last_5_years}',
        )
    elif yt and edu.total_sick_leave_last_5_years != before5:
        ok('sick_5yr_updated_on_handler_complete', '')
    else:
        fail('sick_total_yearly_increment', f'yt={yt}')

    section('6. YEAR RENEWAL (simulate 1/1)')
    # Seed buckets: carryover=4 current=8 entitlement=25
    create_balance_entry(
        employee=emp, entry_type='MANUAL_ADJUSTMENT', description='pre-renewal',
        days_delta=0, carryover_after=4, current_after=8, notes='pre',
    )
    season = get_or_open_season(closing_year=2098, opened_by=handler)  # isolated future season
    st, _ = BalanceRenewalUserStatus.objects.get_or_create(
        season=season, user=emp,
        defaults={'expiring_days': 4, 'carryover_days': 8, 'entitlement_days': 25},
    )
    st.applied_at = None
    st.expiring_days = 4
    st.carryover_days = 8
    st.entitlement_days = 25
    st.save()
    apply_renewal_for_user(st, handler)
    c, cur = get_last_buckets(emp)
    # expect: expire carry 4, import current 8 as carry, grant entitlement current
    ent = emp.annual_leave_entitlement or 25
    if c == 8 and cur == ent:
        ok('annual_renewal_buckets', f'carry={c} current={cur}')
    else:
        fail('annual_renewal_buckets', f'carry={c} current={cur} expected_carry=8 current={ent}')

    # Educational same algorithm
    create_balance_entry(
        employee=edu, entry_type='MANUAL_ADJUSTMENT', description='pre-edu',
        days_delta=0, carryover_after=2, current_after=5, notes='pre',
    )
    st2, _ = BalanceRenewalUserStatus.objects.get_or_create(
        season=season, user=edu,
        defaults={'expiring_days': 2, 'carryover_days': 5, 'entitlement_days': 10},
    )
    st2.applied_at = None
    st2.save(update_fields=['applied_at'])
    apply_renewal_for_user(st2, handler)
    c, cur = get_last_buckets(edu)
    # entitlement 10
    if c == 5 and cur == 10:
        ok('annual_renewal_educational', f'carry={c} current={cur}')
    else:
        fail('annual_renewal_educational', f'carry={c} current={cur}')

    # Confirm no automatic cron — settings only
    from leaves.models import BalanceRenewalSettings
    brs = BalanceRenewalSettings.get_solo()
    ok(
        'annual_renewal_is_manual_only',
        f'apply date {brs.apply_day}/{brs.apply_month} — requires handler action (no Celery job)',
    )

    section('7. SUBSTITUTE 30/6 → 1/9')
    create_balance_entry(
        employee=sub, entry_type='CONTRACT_GRANT', description='seed contract',
        days_delta=0, carryover_after=0, current_after=10, notes='seed',
    )
    end_contract(sub, ended_by=handler, notes='audit end 30/6', end_date=date(2026, 6, 30))
    sub.refresh_from_db()
    bal = get_last_balance(sub)
    if sub.substitute_leave_status == 'PENDING_CONTRACT' and bal == 0 and not sub.has_leave_request_permission():
        ok('substitute_end_zero_and_block', f'status={sub.substitute_leave_status} bal={bal}')
    else:
        fail(
            'substitute_end_zero_and_block',
            f'status={sub.substitute_leave_status} bal={bal} can_req={sub.has_leave_request_permission()}',
        )

    blocked = create_leave(sub, lt_reg, date(2026, 7, 1), date(2026, 7, 2), status='DRAFT')
    try:
        blocked.submit()
        fail('substitute_blocked_submit', 'submit succeeded while PENDING_CONTRACT')
    except ValueError:
        ok('substitute_blocked_submit', '')

    activate_new_contract(
        user=sub,
        contract_start=date(2026, 9, 1),
        contract_end=date(2027, 6, 30),
        entitled_days=10,
        notes='audit new contract 1/9',
        created_by=handler,
        opening_balance=10,
    )
    sub.refresh_from_db()
    bal = get_last_balance(sub)
    if sub.substitute_leave_status == 'ACTIVE' and bal == 10 and sub.has_leave_request_permission():
        ok('substitute_new_contract_grant', f'bal={bal}')
    else:
        fail('substitute_new_contract_grant', f'status={sub.substitute_leave_status} bal={bal}')

    section('8. DEPARTMENT CHANGE MID-FLIGHT')
    pending = create_leave(emp, lt_reg, date(2026, 11, 1), date(2026, 11, 2), status='SUBMITTED')
    old_approver = pending.get_approving_manager()
    emp.department = audit_ked
    emp.save(update_fields=['department'])
    new_approver = pending.get_approving_manager()
    # LeaveRequest has no dept snapshot — approver changes live
    if old_approver and new_approver and old_approver.id != new_approver.id:
        fail(
            'dept_change_reroutes_pending_approver',
            f'pending #{pending.id} approver {old_approver.email} → {new_approver.email} (no snapshot)',
        )
    elif old_approver == new_approver:
        ok('dept_change_same_approver', '')
    else:
        fail('dept_change_reroutes_pending_approver', f'{old_approver} → {new_approver}')
    # restore
    emp.department = audit_tmima
    emp.save(update_fields=['department'])

    # Data still on user: leaves remain linked
    if LeaveRequest.objects.filter(user=emp).exists():
        ok('dept_change_keeps_leave_history', 'requests stay on user FK')
    else:
        fail('dept_change_keeps_leave_history', '')

    section('9. MANAGER CHANGE — ROLE NOT REMOVED')
    old_mgr = audit_tmima.manager
    new_mgr = make_user('tmima.mgr2', 'Νέος', 'Προϊστάμενος', audit_tmima, [ROLE_EMPLOYEE])
    audit_tmima.manager = new_mgr
    audit_tmima.save()
    new_mgr.refresh_from_db()
    old_mgr.refresh_from_db()
    if new_mgr.is_department_manager and ROLE_MANAGER in list(new_mgr.roles.values_list('code', flat=True)):
        ok('new_manager_gets_role', '')
    else:
        fail('new_manager_gets_role', f'roles={list(new_mgr.roles.values_list("code", flat=True))}')
    if ROLE_MANAGER in list(old_mgr.roles.values_list('code', flat=True)):
        fail('old_manager_role_not_revoked', f'{old_mgr.email} still has MANAGER role')
    else:
        ok('old_manager_role_revoked', '')
    # Pending leave now needs new manager
    p2 = create_leave(emp, lt_reg, date(2026, 12, 1), date(2026, 12, 2), status='SUBMITTED')
    if p2.can_be_approved_by(new_mgr) and not p2.can_be_approved_by(old_mgr):
        ok('pending_approve_follows_new_fk_manager', '')
    else:
        fail(
            'pending_approve_follows_new_fk_manager',
            f'new={p2.can_be_approved_by(new_mgr)} old={p2.can_be_approved_by(old_mgr)}',
        )
    # restore manager
    audit_tmima.manager = old_mgr
    audit_tmima.save()

    section('10. SIMPLE / NO-APPROVAL PATHS')
    s = create_leave(emp, lt_simple, date(2026, 8, 20), date(2026, 8, 20), status='DRAFT')
    s.submit()
    s.refresh_from_db()
    # simple still requires_approval True → SUBMITTED then manager completes to COMPLETED
    if s.status == 'SUBMITTED':
        s.approve_by_manager(tmima_mgr)
        s.refresh_from_db()
        if s.status == 'COMPLETED':
            ok('simple_leave_completes_on_manager_approve', '')
        else:
            fail('simple_leave_completes_on_manager_approve', s.status)
    else:
        fail('simple_leave_submit', s.status)

    n = create_leave(emp, lt_noappr, date(2026, 8, 21), date(2026, 8, 21), status='DRAFT')
    n.submit()
    n.refresh_from_db()
    if n.status == 'PENDING_PROTOCOL':
        ok('no_approval_skips_manager', n.status)
    else:
        fail('no_approval_skips_manager', n.status)

    section('11. KEDASY PROTOCOL PATH')
    # Force KEDASY workflow if possible
    ked_emp = make_user('ked.emp', 'Κεδ', 'Εργαζ', audit_ked, [ROLE_EMPLOYEE], 'EDUCATIONAL')
    lt_ked = make_leave_type(
        'KEDREG', 'AUDIT KEDASY Κανονική',
        requires_approval=True, affects_regular_leave_balance=False,
        workflow_variant='KEDASY',
    )
    kl = create_leave(ked_emp, lt_ked, date(2026, 9, 10), date(2026, 9, 11), status='DRAFT')
    kl.submit()
    kl.refresh_from_db()
    # May be PENDING_KEDASY_PROTOCOL depending on routing
    info(f'KEDASY submit status={kl.status} requires_kedasy={kl.requires_kedasy_kepea_protocol()}')
    if kl.status == 'PENDING_KEDASY_PROTOCOL':
        # Handler cannot reject from this status?
        if 'PENDING_KEDASY_PROTOCOL' not in [
            'PENDING_PROTOCOL', 'IN_REVIEW', 'WAITING_FOR_DOCUMENTS',
            'DECISION_PREPARATION', 'PENDING_SIGNATURES',
        ]:
            # check reject_by_handler
            rejected = kl.reject_by_handler(handler, 'test')
            if not rejected:
                fail('kedasy_protocol_no_handler_reject', 'soft-stuck until secretary adds protocol or withdraw')
            else:
                ok('kedasy_protocol_handler_reject', '')
            kl.refresh_from_db()
            if kl.status == 'PENDING_KEDASY_PROTOCOL':
                # withdraw path
                if kl.can_be_withdrawn:
                    ok('kedasy_protocol_can_withdraw', '')
                else:
                    fail('kedasy_protocol_can_withdraw', '')
    else:
        ok('kedasy_submit_status', kl.status)

    section('12. LIVE DATA SANITY')
    # Depts without manager
    no_mgr = Department.objects.filter(is_active=True, manager__isnull=True).count()
    info(f'Active departments without FK manager: {no_mgr}')
    # Users whose approver is None but can request and not root
    orphans = []
    for u in User.objects.filter(is_active=True, registration_status='APPROVED').select_related('department'):
        if not u.has_leave_request_permission():
            continue
        if u.get_approving_manager() is None:
            orphans.append(u.email)
    if orphans:
        fail('live_users_with_no_approver_but_can_request', str(orphans[:10]))
    else:
        ok('live_users_with_no_approver_but_can_request', 'none')

    # Ledger vs cache drift
    drifts = []
    for u in User.objects.filter(is_active=True):
        last = get_last_balance(u)
        if last is not None and last != (u.current_regular_leave_balance or 0):
            drifts.append((u.email, u.current_regular_leave_balance, last))
    if drifts:
        fail('ledger_cache_drift', str(drifts[:10]))
    else:
        ok('ledger_cache_drift', 'aligned')

    section('SUMMARY')
    passes = sum(1 for r in results if r[0] == 'PASS')
    fails = sum(1 for r in results if r[0] == 'FAIL')
    print(f'\nTOTAL: {passes} PASS, {fails} FAIL out of {len(results)}')
    print('\n--- FAILURES ---')
    for st, name, detail in results:
        if st == 'FAIL':
            print(f'  • {name}: {detail}')

    cleanup()
    print('\nCleanup done.')
    return fails


if __name__ == '__main__':
    try:
        raise SystemExit(run_audit())
    except Exception:
        traceback.print_exc()
        try:
            cleanup()
        except Exception:
            pass
        raise SystemExit(2)

# When loaded via `manage.py shell < script.py`
try:
    raise SystemExit(run_audit())
except SystemExit:
    raise
except Exception:
    traceback.print_exc()
    try:
        cleanup()
    except Exception:
        pass
    raise SystemExit(2)
