"""
Management command για data retention policy (GDPR compliance)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from leaves.models import LeaveRequest, LeaveAccessLog, LeaveActionLog


class Command(BaseCommand):
    help = 'Καθαρισμός παλαιών δεδομένων σύμφωνα με data retention policy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Εμφάνιση αλλαγών χωρίς διαγραφή',
        )
        parser.add_argument(
            '--logs-years',
            type=int,
            default=7,
            help='Έτη διατήρησης logs (default: 7)',
        )
        parser.add_argument(
            '--requests-years',
            type=int,
            default=5,
            help='Έτη διατήρησης αιτήσεων (default: 5)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        logs_years = options['logs_years']
        requests_years = options['requests_years']

        logs_cutoff = timezone.now() - timedelta(days=logs_years * 365)
        requests_cutoff = timezone.now() - timedelta(days=requests_years * 365)

        self.stdout.write(self.style.SUCCESS(
            f'=== Data Retention Cleanup {"(DRY RUN)" if dry_run else ""} ==='
        ))

        # Καθαρισμός παλαιών access logs
        old_access_logs = LeaveAccessLog.objects.filter(timestamp__lt=logs_cutoff)
        access_count = old_access_logs.count()
        if not dry_run:
            old_access_logs.delete()
        self.stdout.write(f'Access Logs: {access_count} διαγραφές')

        # Καθαρισμός παλαιών action logs
        old_action_logs = LeaveActionLog.objects.filter(timestamp__lt=logs_cutoff)
        action_count = old_action_logs.count()
        if not dry_run:
            old_action_logs.delete()
        self.stdout.write(f'Action Logs: {action_count} διαγραφές')

        # Σημείωση: Οι αιτήσεις ΔΕΝ διαγράφονται αυτόματα,
        # μόνο αν είναι σε terminal state (COMPLETED, REJECTED, WITHDRAWN)
        # και έχουν περάσει τα requests_years
        terminal_statuses = ['COMPLETED', 'REJECTED_OPERATOR', 'REJECTED_MANAGER',
                           'WITHDRAWN_BY_REQUESTER', 'WITHDRAWN_COMPLETED', 'DELETED_BY_HANDLER']
        old_requests = LeaveRequest.objects.filter(
            status__in=terminal_statuses,
            completed_at__lt=requests_cutoff
        )
        requests_count = old_requests.count()
        if not dry_run:
            # Αντί για διαγραφή, ανώνυμοποίηση
            old_requests.update(
                description='[ΑΝΩΝΥΜΟΠΟΙΗΘΗΚΕ]',
                rejection_reason='[ΑΝΩΝΥΜΟΠΟΙΗΘΗΚΕ]',
                manager_comments='[ΑΝΩΝΥΜΟΠΟΙΗΘΗΚΕ]',
                processing_comments='[ΑΝΩΝΥΜΟΠΟΙΗΘΗΚΕ]'
            )
        self.stdout.write(f'Leave Requests: {requests_count} ανωνυμοποιήσεις')

        self.stdout.write(self.style.SUCCESS('\nΟλοκληρώθηκε!'))
        if dry_run:
            self.stdout.write(self.style.WARNING('Αυτό ήταν DRY RUN - δεν έγιναν αλλαγές.'))
