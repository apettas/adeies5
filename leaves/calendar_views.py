from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta, date
import calendar
from .models import LeaveRequest, LeavePeriod
from django.contrib.auth import get_user_model

User = get_user_model()


@login_required
def leave_calendar_view(request, year=None, month=None):
    """Ημερολόγιο αδειών για προϊσταμένους τμημάτων"""
    if not request.user.is_department_manager:
        raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
    
    # Καθορισμός μήνα και έτους
    today = timezone.now().date()
    if year is None:
        year = today.year
    if month is None:
        month = today.month
    
    year = int(year)
    month = int(month)
    
    # Δημιουργία ημερομηνιών για τον μήνα
    first_day = date(year, month, 1)
    if month == 12:
        last_day = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = date(year, month + 1, 1) - timedelta(days=1)
    
    # Υπολογισμός προηγούμενου και επόμενου μήνα
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    
    # Βρίσκω όλους τους υφισταμένους του προϊσταμένου
    subordinates = request.user.get_subordinates()
    employees_to_include = list(subordinates)
    
    # Αν ο χρήστης είναι προϊστάμενος ΚΕΔΑΣΥ, προσθέτω και χρήστες από ΣΔΕΥ
    if (request.user.department and
        request.user.department.department_type and
        request.user.department.department_type.code == 'KEDASY'):
        
        sdeu_users = User.objects.filter(
            department__department_type__code='SDEY',
            department__parent_department=request.user.department,
            is_active=True
        )
        employees_to_include.extend(list(sdeu_users))
    
    # Βρίσκω όλες τις αιτήσεις αδειών που επηρεάζουν αυτόν τον μήνα
    # Συμπεριλαμβάνω αιτήσεις που είναι εγκεκριμένες ή ολοκληρωμένες
    approved_statuses = ['APPROVED_MANAGER', 'PENDING_KEDASY_KEPEA_PROTOCOL', 'FOR_PROTOCOL_PDEDE', 
                        'PENDING_DOCUMENTS', 'UNDER_PROCESSING', 'COMPLETED']
    
    leave_requests = LeaveRequest.objects.filter(
        user__in=employees_to_include,
        status__in=approved_statuses
    ).select_related('user', 'leave_type').prefetch_related('periods')
    
    # Φιλτράρω τις περιόδους που τέμνουν με τον τρέχοντα μήνα
    month_periods = []
    for leave_request in leave_requests:
        for period in leave_request.periods.all():
            # Έλεγχος αν η περίοδος τέμνει με τον μήνα
            if (period.start_date <= last_day and period.end_date >= first_day):
                # Κλιπάρω τις ημερομηνίες στον μήνα
                period_start = max(period.start_date, first_day)
                period_end = min(period.end_date, last_day)
                
                month_periods.append({
                    'request': leave_request,
                    'period': period,
                    'period_start': period_start,
                    'period_end': period_end,
                    'user': leave_request.user,
                    'leave_type': leave_request.leave_type,
                    'status': leave_request.status
                })
    
    # Δημιουργία του ημερολογίου
    cal = calendar.Calendar(firstweekday=0)  # Δευτέρα = 0
    month_days = cal.monthdayscalendar(year, month)
    
    # Ονόματα ημερών στα ελληνικά
    day_names = ['Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο', 'Κυριακή']
    
    # Ονόματα μηνών στα ελληνικά
    month_names = [
        '', 'Ιανουάριος', 'Φεβρουάριος', 'Μάρτιος', 'Απρίλιος', 'Μάιος', 'Ιούνιος',
        'Ιούλιος', 'Αύγουστος', 'Σεπτέμβριος', 'Οκτώβριος', 'Νοέμβριος', 'Δεκέμβριος'
    ]
    
    # Δημιουργία δομής ημερολογίου με events
    calendar_weeks = []
    for week in month_days:
        calendar_days = []
        for day in week:
            if day == 0:
                calendar_days.append({
                    'day': '',
                    'date': None,
                    'is_today': False,
                    'is_weekend': False,
                    'events': []
                })
            else:
                day_date = date(year, month, day)
                weekday = day_date.weekday()  # 0 = Δευτέρα, 6 = Κυριακή
                
                # Βρίσκω τα events για αυτή την ημέρα
                day_events = []
                for period in month_periods:
                    if period['period_start'] <= day_date <= period['period_end']:
                        day_events.append({
                            'user_name': period['user'].full_name,
                            'leave_type': period['leave_type'].name,
                            'leave_type_id': period['leave_type'].id,
                            'status': period['status'],
                            'request_id': period['request'].id
                        })
                
                calendar_days.append({
                    'day': day,
                    'date': day_date,
                    'is_today': day_date == today,
                    'is_weekend': weekday >= 5,  # Σάββατο (5) και Κυριακή (6)
                    'events': day_events
                })
        calendar_weeks.append(calendar_days)
    
    # Χρώματα για τους τύπους αδειών
    leave_type_colors = get_leave_type_colors()
    
    # Προσθήκη χρωμάτων στα events
    for week in calendar_weeks:
        for day in week:
            for event in day['events']:
                event['color'] = leave_type_colors.get(event['leave_type_id'], '#007bff')
    
    context = {
        'calendar_weeks': calendar_weeks,
        'day_names': day_names,
        'current_month': month_names[month],
        'current_year': year,
        'current_month_num': month,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'today': today,
        'leave_type_colors': leave_type_colors,
        'total_employees': len(employees_to_include),
        'total_requests': len(month_periods),
    }
    
    return render(request, 'leaves/calendar.html', context)


def get_leave_type_colors():
    """Επιστρέφει χρώματα για κάθε τύπο άδειας"""
    from .models import LeaveType
    
    # Προκαθορισμένα χρώματα Bootstrap και επιπλέον
    colors = [
        '#007bff',  # Primary blue
        '#28a745',  # Success green
        '#dc3545',  # Danger red
        '#ffc107',  # Warning yellow
        '#17a2b8',  # Info cyan
        '#6f42c1',  # Purple
        '#e83e8c',  # Pink
        '#fd7e14',  # Orange
        '#20c997',  # Teal
        '#6c757d',  # Secondary gray
        '#795548',  # Brown
        '#607d8b',  # Blue gray
        '#f44336',  # Red
        '#e91e63',  # Pink
        '#9c27b0',  # Purple
        '#673ab7',  # Deep purple
        '#3f51b5',  # Indigo
        '#2196f3',  # Blue
        '#03a9f4',  # Light blue
        '#00bcd4',  # Cyan
    ]
    
    leave_types = LeaveType.objects.filter(is_active=True).order_by('id')
    type_colors = {}
    
    for i, leave_type in enumerate(leave_types):
        color_index = i % len(colors)
        type_colors[leave_type.id] = colors[color_index]
    
    return type_colors