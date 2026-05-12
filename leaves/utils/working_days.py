"""
Υπολογισμός εργάσιμων ημερών για αιτήσεις αδειών
Αφαιρεί Σαββατοκύριακα και δημόσιες αργίες
"""
from datetime import date, timedelta
from django.utils import timezone


def get_holidays_in_range(start_date, end_date):
    """
    Επιστρέφει λίστα δημόσιων αργιών εντός του διαστήματος.
    Δεν συμπεριλαμβάνει αργίες που πέφτουν Σαββατοκύριακο.
    """
    from leaves.models import PublicHoliday

    holidays = PublicHoliday.objects.filter(
        date__gte=start_date,
        date__lte=end_date,
        is_active=True
    )

    # Φιλτράρουμε αργίες που πέφτουν Σαββατοκύριακο
    working_day_holidays = []
    for holiday in holidays:
        weekday = holiday.date.weekday()
        if weekday < 5:  # 0-4 = Δευτέρα-Παρασκευή
            working_day_holidays.append(holiday.date)

    return working_day_holidays


def is_working_day(check_date):
    """
    Ελέγχει αν μια ημερομηνία είναι εργάσιμη ημέρα.
    False αν είναι Σαββατοκύριακο ή δημόσια αργία.
    """
    # Σαββατοκύριακο
    if check_date.weekday() >= 5:
        return False

    # Δημόσια αργία
    from leaves.models import PublicHoliday
    if PublicHoliday.objects.filter(
        date=check_date,
        is_active=True
    ).exists():
        return False

    return True


def calculate_working_days(start_date, end_date):
    """
    Υπολογίζει τον αριθμό εργάσιμων ημερών μεταξύ δύο ημερομηνιών.
    Αφαιρεί Σαββατοκύριακα και δημόσιες αργίες που πέφτουν καθημερινή.

    Args:
        start_date: Ημερομηνία έναρξης
        end_date: Ημερομηνία λήξης

    Returns:
        int: Αριθμός εργάσιμων ημερών
    """
    if start_date > end_date:
        return 0

    # Αν same day, check if it's a working day
    if start_date == end_date:
        return 1 if is_working_day(start_date) else 0

    # Count working days
    working_days = 0
    current_date = start_date

    # Get all holidays in range once (for efficiency)
    holiday_dates = set(get_holidays_in_range(start_date, end_date))

    while current_date <= end_date:
        weekday = current_date.weekday()
        # 0-4 = Δευτέρα-Παρασκευή
        if weekday < 5 and current_date not in holiday_dates:
            working_days += 1
        current_date += timedelta(days=1)

    return working_days


def get_leave_periods_working_days(periods):
    """
    Υπολογίζει συνολικές εργάσιμες ημέρες από πολλαπλά διαστήματα.
    Χρησιμοποιείται στη φόρμα αίτησης άδειας.

    Args:
        periods: list of dicts [{'start_date': ..., 'end_date': ...}, ...]

    Returns:
        int: Συνολικές εργάσιμες ημέρες
    """
    total = 0
    for period in periods:
        if period.get('start_date') and period.get('end_date'):
            total += calculate_working_days(
                period['start_date'],
                period['end_date']
            )
    return total
