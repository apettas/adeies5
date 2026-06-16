"""
Εκτεταμένο τεστ ολόκληρου του workflow αδειών.
Εκκαθάριση όλων των δοκιμαστικών αιτήσεων και δημιουργία νέων.

Χρήση: echo "yes" | docker compose exec web python manage.py test_full_workflow
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from accounts.models import User
from leaves.models import LeaveRequest, LeavePeriod, LeaveType, LeaveActionLog, LeaveAccessLog, SecureFile
from notifications.models import Notification
from django.conf import settings
import os, shutil


class Command(BaseCommand):
    help = 'Εκτελεί εκτεταμένο τεστ workflow αδειών'

    def handle(self, *args, **options):
        self.stdout.write('=== TEST FULL WORKFLOW ===\n')
        self.cleanup()
        self.run()
        self.stdout.write(self.style.SUCCESS('\n*** ALL TESTS PASSED ***'))

    @transaction.atomic
    def cleanup(self):
        self.stdout.write('--- CLEANUP ---')
        for m in [LeaveActionLog, LeaveAccessLog, SecureFile, LeavePeriod, LeaveRequest, Notification]:
            c = m.objects.all().delete()[0]
            self.stdout.write(f'  {m.__name__}: {c}')
        private_root = getattr(settings, 'PRIVATE_MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'private_media'))
        p = os.path.join(private_root, 'leave_requests')
        if os.path.exists(p): shutil.rmtree(p)
        User.objects.exclude(email='pdede@sch.gr').update(
            annual_leave_entitlement=25,
            sick_leave_with_declaration=2, sick_days_current_year=0,
            total_sick_leave_last_5_years=0, current_regular_leave_balance=25)
        self.stdout.write('  Balances reset')

    def create(self, u, lt, days, desc='', attach=False):
        sd = date.today() + timedelta(days=1)
        lr = LeaveRequest.objects.create(user=u, leave_type=lt, description=desc, days=days, status='DRAFT')
        LeavePeriod.objects.create(leave_request=lr, start_date=sd, end_date=sd + timedelta(days=days - 1))
        if attach:
            SecureFile.objects.create(leave_request=lr, original_filename='t.pdf', file_path='/dev/null',
                file_size=100, content_type='application/pdf', encryption_key='00' * 32, uploaded_by=u)
        return lr

    def s(self, lr, exp):
        lr.submit(); lr.refresh_from_db()
        assert lr.status == exp, f'{lr.user.email} {lr.leave_type.code}: {lr.status} != {exp}'
        self.stdout.write(f'  \u2713 {lr.user.email:30s} | {lr.leave_type.code:10s} | submit \u2192 {lr.status}')
        return lr

    def p(self, lr, user, exp='SUBMITTED'):
        lr.add_kedasy_kepea_protocol(protocol_number=f'K/{lr.id}', protocol_date=timezone.now().date(), user=user)
        lr.refresh_from_db()
        assert lr.status == exp, f'{lr.user.email}: protocol \u2192 {lr.status} != {exp}'
        self.stdout.write(f'  \u2713 {lr.user.email:30s} | protocol by {user.email:20s} | \u2192 {lr.status}')
        return lr

    def a(self, lr, mgr, exp='PENDING_PROTOCOL'):
        lr.approve_by_manager(mgr); lr.refresh_from_db()
        assert lr.status == exp, f'{lr.user.email}: approve \u2192 {lr.status} != {exp}'
        self.stdout.write(f'  \u2713 {lr.user.email:30s} | approved by {mgr.email:20s} | \u2192 {lr.status}')
        return lr

    def r(self, lr, mgr, reason='Load', exp='SUPERVISOR_REJECTED'):
        lr.reject_by_manager(mgr, reason); lr.refresh_from_db()
        assert lr.status == exp, f'{lr.user.email}: reject \u2192 {lr.status} != {exp}'
        self.stdout.write(f'  \u2713 {lr.user.email:30s} | rejected by {mgr.email:20s} | \u2192 {lr.status}')
        return lr

    def w(self, lr, exp='CANCELLED_BY_APPLICANT'):
        lr.withdraw_by_requester(lr.user); lr.refresh_from_db()
        assert lr.status == exp, f'{lr.user.email}: withdraw \u2192 {lr.status} != {exp}'
        self.stdout.write(f'  \u2713 {lr.user.email:30s} | withdrawn')
        return lr

    def run(self):
        u = {e.split('@')[0]: User.objects.get(email=e) for e in [
            'karayan@sch.gr', 'baladakis@sch.gr', 'kotsonis@sch.gr',
            'delegkos@sch.gr', 'kizilou@sch.gr',
            'sdeiagriniou@sch.gr', 'agorastou@sch.gr', 'xabesis@sch.gr', 'apettas@sch.gr']}
        lt1 = LeaveType.objects.get(code='LT001')  # regular, req_approval=True, affects_balance=True
        lt2 = LeaveType.objects.get(code='LT002')  # sick YD, req_approval=False
        lt3 = LeaveType.objects.get(code='LT003')  # sick 10day, req_approval=False

        # ========== A: REGULAR LEAVE ==========
        self.stdout.write('\n-- A: Regular leave (balance decreases) --')
        b = u['karayan'].leave_balance
        self.a(self.s(self.create(u['karayan'], lt1, 5), 'SUBMITTED'), u['apettas'])
        u['karayan'].refresh_from_db()
        self.stdout.write(f'  Balance: {b} \u2192 {u["karayan"].leave_balance}')

        # PDEDE manager
        m = u['delegkos'].get_approving_manager()
        self.s(self.create(u['delegkos'], lt1, 3), 'SUBMITTED')
        if m: self.a(LeaveRequest.objects.filter(user=u['delegkos'], status='SUBMITTED').last(), m)

        # Autotelous manager
        self.s(self.create(u['kizilou'], lt1, 4), 'SUBMITTED')
        mk = u['kizilou'].get_approving_manager()
        self.stdout.write(f'  kizilou manager: {mk}')

        # SDEY: submit -> PENDING_KEDASY_PROTOCOL -> protocol -> approve
        lr = self.s(self.create(u['sdeiagriniou'], lt1, 5), 'PENDING_KEDASY_PROTOCOL')
        lr = self.p(lr, u['xabesis'])
        self.a(lr, u['agorastou'])

        # KEDASY manager
        lr = self.s(self.create(u['agorastou'], lt1, 2), 'PENDING_KEDASY_PROTOCOL')
        lr = self.p(lr, u['xabesis'])

        # KEDASY secretary
        lr = self.s(self.create(u['xabesis'], lt1, 1), 'PENDING_KEDASY_PROTOCOL')
        lr = self.p(lr, u['agorastou'])
        mx = u['xabesis'].get_approving_manager()
        if mx: self.a(lr, mx)

        # ========== B: SICK LEAVE YD ==========
        self.stdout.write('\n-- B: Sick leave YD (zero out) --')
        # requires_approval=False -> submit -> PENDING_PROTOCOL (or PENDING_KEDASY_PROTOCOL for KEDASY)
        self.s(self.create(u['karayan'], lt2, 3), 'PENDING_PROTOCOL')
        self.s(self.create(u['karayan'], lt2, 2), 'PENDING_PROTOCOL')
        self.s(self.create(u['karayan'], lt2, 1), 'PENDING_PROTOCOL')
        u['karayan'].refresh_from_db()
        self.stdout.write(f'  karayan sick_yd: {u["karayan"].sick_leave_with_declaration}')

        # SDEY sick YD -> PENDING_KEDASY_PROTOCOL -> protocol bypasses approval
        lr = self.s(self.create(u['sdeiagriniou'], lt2, 1), 'PENDING_KEDASY_PROTOCOL')
        self.p(lr, u['xabesis'], 'PENDING_PROTOCOL')
        u['sdeiagriniou'].refresh_from_db()

        # ========== C: 10-DAY SICK LEAVE ==========
        self.stdout.write('\n-- C: 10-day sick leave --')
        u['baladakis'].refresh_from_db()
        self.stdout.write(f'  baladakis sick_days_year: {u["baladakis"].sick_days_current_year}')
        self.s(self.create(u['baladakis'], lt3, 10), 'PENDING_PROTOCOL')

        # ========== D: REJECTION ==========
        self.stdout.write('\n-- D: Rejection --')
        lr = self.create(u['kotsonis'], lt1, 3, desc='Reject me')
        self.r(self.s(lr, 'SUBMITTED'), u['apettas'], 'Too busy')

        # ========== E: WITHDRAWAL ==========
        self.stdout.write('\n-- E: Withdrawal --')
        self.w(self.s(self.create(u['karayan'], lt1, 2, desc='Withdraw'), 'SUBMITTED'))
        self.w(self.s(self.create(u['sdeiagriniou'], lt1, 2, desc='Withdraw KEDASY'), 'PENDING_KEDASY_PROTOCOL'))

        # ========== F: WITH ATTACHMENTS ==========
        self.stdout.write('\n-- F: With attachments --')
        lr = self.create(u['karayan'], lt1, 3, attach=True)
        assert lr.attachments.count() == 1
        self.a(self.s(lr, 'SUBMITTED'), u['apettas'])

        # ========== G: DOCUMENTS ==========
        self.stdout.write('\n-- G: Documents request/provide --')
        lr = self.create(u['kotsonis'], lt1, 5, desc='Need docs')
        lr.status = 'WAITING_FOR_DOCUMENTS'; lr.save()
        SecureFile.objects.create(leave_request=lr, original_filename='doc.pdf', file_path='/dev/null',
            file_size=200, content_type='application/pdf', encryption_key='00' * 32, uploaded_by=u['apettas'])
        lr.provide_documents(handler=u['apettas'], notes='Done')
        lr.refresh_from_db()
        self.stdout.write(f'  After provide: {lr.status}')
        assert lr.status in ['IN_REVIEW', 'PENDING_PROTOCOL']

        # ========== H: SDEY PROTOCOL BY MANAGER ==========
        self.stdout.write('\n-- H: SDEY protocol by KEDASY manager --')
        lr = self.s(self.create(u['sdeiagriniou'], lt1, 3), 'PENDING_KEDASY_PROTOCOL')
        lr = self.p(lr, u['agorastou'])
        self.a(lr, u['agorastou'])

        # ========== I: PDEDE FULL FLOW ==========
        self.stdout.write('\n-- I: PDEDE full flow --')
        self.a(self.s(self.create(u['kotsonis'], lt1, 5), 'SUBMITTED'), u['apettas'])

        # ========== J: BALANCE REVIEW ==========
        self.stdout.write('\n-- J: Final balances --')
        for e in ['karayan@sch.gr', 'baladakis@sch.gr', 'sdeiagriniou@sch.gr', 'agorastou@sch.gr']:
            uu = User.objects.get(email=e)
            self.stdout.write(f'  {e:30s} leave_balance={uu.leave_balance}')
