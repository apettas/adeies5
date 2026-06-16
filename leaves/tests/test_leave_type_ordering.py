"""Tests σειράς τύπων άδειας στο dropdown."""
from django.test import TestCase

from leaves.forms import LeaveRequestForm
from leaves.models import LeaveType
from leaves.utils.leave_type_ordering import PREFERRED_LEAVE_TYPE_CODES


class LeaveTypeOrderingTests(TestCase):
    def setUp(self):
        LeaveType.objects.all().delete()
        LeaveType.objects.create(code='LT099', name='Ωμικρόν Άδεια', is_active=True)
        LeaveType.objects.create(code='LT030', name='Κανονική Άδεια', is_active=True)
        LeaveType.objects.create(code='LT022', name='Αναρρωτική Άδεια με Ιατρική Γνωμάτευση', is_active=True)
        LeaveType.objects.create(code='LT001', name='Αδεια Αλφα', is_active=True)
        LeaveType.objects.create(code='LT023', name='Αναρρωτική Άδεια με ΥΔ', is_active=True)
        LeaveType.objects.create(code='LT002', name='Άδεια παρακολούθησης σχολικής επίδοσης τέκνου', is_active=True)

    def test_form_shows_preferred_leave_types_first(self):
        form = LeaveRequestForm()
        codes = list(form.fields['leave_type'].queryset.values_list('code', flat=True))
        self.assertEqual(codes[:4], list(PREFERRED_LEAVE_TYPE_CODES))
        self.assertEqual(codes[4], 'LT001')
        self.assertEqual(codes[5], 'LT099')
