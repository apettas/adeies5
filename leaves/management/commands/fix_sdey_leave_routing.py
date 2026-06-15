"""Διόρθωση αιτήσεων ΣΔΕΥ που υποβλήθηκαν λάθος ως SUBMITTED (legacy τύπος SDEI)."""

from django.core.management.base import BaseCommand
from django.db.models import Q

from accounts.department_utils import is_sdey_under_kedasy
from leaves.models import LeaveRequest


class Command(BaseCommand):
    help = (
        'Επαναφέρει αιτήσεις ΣΔΕΥ/ΚΕΔΑΣΥ σε PENDING_KEDASY_PROTOCOL '
        'όταν έχουν κολλήσει σε SUBMITTED χωρίς πρωτόκολλο ΚΕΔΑΣΥ'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--request-id',
            type=int,
            help='Διόρθωση συγκεκριμένης αίτησης (αλλιώς όλες οι επιλέξιμες)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Μόνο προεπισκόπηση, χωρίς αποθήκευση',
        )

    def handle(self, *args, **options):
        request_id = options.get('request_id')
        dry_run = options['dry_run']

        qs = LeaveRequest.objects.filter(
            status='SUBMITTED',
        ).filter(
            Q(kedasy_kepea_protocol_number__isnull=True)
            | Q(kedasy_kepea_protocol_number='')
        ).select_related('user__department__department_type', 'user__department__parent_department__department_type')

        if request_id:
            qs = qs.filter(pk=request_id)

        fixed = 0
        for leave_request in qs:
            department = leave_request.user.department
            if not is_sdey_under_kedasy(department):
                continue

            dept_code = department.department_type.code if department and department.department_type else '?'
            self.stdout.write(
                f"#{leave_request.pk}: {leave_request.user.email} "
                f"({dept_code}) SUBMITTED → PENDING_KEDASY_PROTOCOL"
            )
            if not dry_run:
                leave_request.status = 'PENDING_KEDASY_PROTOCOL'
                leave_request.save(update_fields=['status'])
            fixed += 1

        suffix = ' (dry-run)' if dry_run else ''
        self.stdout.write(self.style.SUCCESS(f'Ολοκληρώθηκε: {fixed} αίτηση/εις{suffix}'))
