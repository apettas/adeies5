"""Σειρά εμφάνισης τύπων άδειας στο dropdown δημιουργίας αίτησης."""
from django.db.models import Case, IntegerField, Value, When

from leaves.models import LeaveType

# Συχνά ζητούμενοι τύποι — εμφανίζονται πρώτοι, μετά τα υπόλοιπα αλφαβητικά.
PREFERRED_LEAVE_TYPE_CODES = (
    'LT030',  # Κανονική Άδεια
    'LT022',  # Αναρρωτική Άδεια με Ιατρική Γνωμάτευση
    'LT023',  # Αναρρωτική Άδεια με ΥΔ
    'LT002',  # Άδεια παρακολούθησης σχολικής επίδοσης τέκνου
)


def get_ordered_active_leave_types(queryset=None):
    """Ενεργοί τύποι: πρώτα οι preferred κωδικοί, μετά αλφαβητικά."""
    qs = queryset if queryset is not None else LeaveType.objects.filter(is_active=True)
    whens = [
        When(code=code, then=Value(index))
        for index, code in enumerate(PREFERRED_LEAVE_TYPE_CODES)
    ]
    return qs.annotate(
        _preferred_order=Case(
            *whens,
            default=Value(len(PREFERRED_LEAVE_TYPE_CODES)),
            output_field=IntegerField(),
        )
    ).order_by('_preferred_order', 'name')
