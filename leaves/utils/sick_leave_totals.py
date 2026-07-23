"""Ενημέρωση cache πεδίων αναρρωτικών στον χρήστη από YearlySickLeaveTotal."""
from django.db.models import Sum
from django.utils import timezone

from leaves.models import YearlySickLeaveTotal

# Inclusive window: current_year-5 … current_year (6 calendar years).
# Παλαιότερες εγγραφές μένουν στη βάση αλλά δεν μετράνε στο άθροισμα.
SICK_HISTORY_YEAR_SPAN = 5


def sick_history_year_range(current_year=None):
    current_year = current_year or timezone.now().year
    return current_year - SICK_HISTORY_YEAR_SPAN, current_year


def refresh_user_sick_leave_totals(user, current_year=None):
    """
    Συγχρονίζει sick_days_current_year και total_sick_leave_last_5_years
    από τις εγγραφές YearlySickLeaveTotal.
    """
    current_year = current_year or timezone.now().year
    start_year, end_year = sick_history_year_range(current_year)

    yearly = YearlySickLeaveTotal.objects.filter(
        employee=user, year=current_year,
    ).first()
    user.sick_days_current_year = yearly.total_days if yearly else 0

    last_n = YearlySickLeaveTotal.objects.filter(
        employee=user,
        year__gte=start_year,
        year__lte=end_year,
    ).aggregate(total=Sum('total_days'))['total'] or 0
    user.total_sick_leave_last_5_years = last_n
    user.save(update_fields=['sick_days_current_year', 'total_sick_leave_last_5_years'])
    return user
