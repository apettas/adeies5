from datetime import date

from django.test import TestCase

from accounts.tests.test_data import TestDataMixin
from leaves.decision_helpers import format_decision_dates_compact, build_decision_body_html
from leaves.models import LeavePeriod, LeaveRequest, LeaveType


class DecisionHelpersTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.leave_type = LeaveType.objects.create(
            name='Αναρρωτική Άδεια',
            code='SICK',
            decision_text='αναρρωτική άδεια',
            requires_approval=True,
            max_days=30,
        )

    def _create_request_with_periods(self, periods):
        leave_request = LeaveRequest.objects.create(
            user=self.employee,
            leave_type=self.leave_type,
            description='Test',
            status='IN_REVIEW',
        )
        for start, end in periods:
            LeavePeriod.objects.create(
                leave_request=leave_request,
                start_date=start,
                end_date=end,
            )
        return leave_request

    def test_single_day_period(self):
        lr = self._create_request_with_periods([(date(2026, 6, 15), date(2026, 6, 15))])
        self.assertEqual(format_decision_dates_compact(lr), 'στις 15-6-2026')

    def test_contiguous_multi_day_period(self):
        lr = self._create_request_with_periods([(date(2026, 6, 15), date(2026, 6, 17))])
        self.assertEqual(
            format_decision_dates_compact(lr),
            'από 15-6-2026 έως και 17-6-2026',
        )

    def test_two_separate_single_day_periods(self):
        lr = self._create_request_with_periods([
            (date(2026, 6, 15), date(2026, 6, 15)),
            (date(2026, 6, 22), date(2026, 6, 22)),
        ])
        self.assertEqual(
            format_decision_dates_compact(lr),
            'στις 15-6-2026 και 22-6-2026',
        )
        body = build_decision_body_html(lr)
        self.assertIn('δύο (2) εργάσιμες ημέρες', body)
        self.assertNotIn('έως και 22-6-2026', body)

    def test_mixed_period_lengths(self):
        lr = self._create_request_with_periods([
            (date(2026, 6, 15), date(2026, 6, 15)),
            (date(2026, 6, 20), date(2026, 6, 22)),
        ])
        self.assertEqual(
            format_decision_dates_compact(lr),
            'στις 15-6-2026 και από 20-6-2026 έως και 22-6-2026',
        )
