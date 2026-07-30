"""Tests για προειδοποίηση επικάλυψης διαστημάτων μεταξύ αιτήσεων."""
from datetime import date

from django.test import TestCase

from accounts.tests.test_data import TestDataMixin
from leaves.models import LeavePeriod, LeaveRequest, LeaveType
from leaves.utils.period_overlap import (
    find_overlapping_requests_for_periods,
    serialize_user_leave_periods_for_overlap,
)


class PeriodOverlapUtilsTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.leave_type = LeaveType.objects.create(
            name='Κανονική',
            code='OV_ANNUAL',
            requires_approval=True,
            affects_regular_leave_balance=True,
        )
        self.other_type = LeaveType.objects.create(
            name='Αναρρωτική',
            code='OV_SICK',
            requires_approval=True,
        )

    def _create_request(self, status, start, end, leave_type=None):
        req = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=leave_type or self.leave_type,
            description='overlap test',
            status=status,
        )
        LeavePeriod.objects.create(leave_request=req, start_date=start, end_date=end)
        return req

    def test_serialize_includes_active_requests(self):
        req = self._create_request('SUBMITTED', date(2026, 7, 1), date(2026, 7, 10))
        data = serialize_user_leave_periods_for_overlap(self.employee)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['id'], req.id)
        self.assertEqual(data[0]['leave_type'], 'Κανονική')
        self.assertEqual(data[0]['periods'][0]['start'], '2026-07-01')
        self.assertEqual(data[0]['periods'][0]['end'], '2026-07-10')

    def test_serialize_excludes_rejected_and_cancelled(self):
        self._create_request('REJECTED_BY_LEAVES_DEPT', date(2026, 7, 1), date(2026, 7, 10))
        self._create_request('CANCELLED_BY_APPLICANT', date(2026, 8, 1), date(2026, 8, 5))
        data = serialize_user_leave_periods_for_overlap(self.employee)
        self.assertEqual(data, [])

    def test_find_partial_overlap(self):
        first = self._create_request(
            'COMPLETED', date(2026, 7, 1), date(2026, 7, 10), leave_type=self.leave_type,
        )
        conflicts = find_overlapping_requests_for_periods(
            self.employee,
            [{'start_date': date(2026, 7, 8), 'end_date': date(2026, 7, 15)}],
        )
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]['id'], first.id)
        self.assertEqual(conflicts[0]['leave_type'], 'Κανονική')

    def test_no_overlap_returns_empty(self):
        self._create_request('SUBMITTED', date(2026, 7, 1), date(2026, 7, 5))
        conflicts = find_overlapping_requests_for_periods(
            self.employee,
            [{'start_date': date(2026, 7, 6), 'end_date': date(2026, 7, 10)}],
        )
        self.assertEqual(conflicts, [])

    def test_create_page_includes_overlap_json(self):
        self._create_request('SUBMITTED', date(2026, 7, 1), date(2026, 7, 10))
        self.client.force_login(self.employee)
        response = self.client.get('/leaves/create/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'existing-period-overlap-warning')
        self.assertContains(response, '2026-07-01')
        self.assertContains(response, 'Κανονική')
