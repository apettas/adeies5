"""Views για ενότητα Αναφορές (χειριστές αδειών)."""
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views.generic import TemplateView

from accounts.models import Department


def _require_handler(user):
    if not (user.is_leave_handler or user.is_administrator):
        raise PermissionDenied('Μόνο χειριστές αδειών έχουν πρόσβαση.')


class ReportsIndexView(LoginRequiredMixin, TemplateView):
    """Κεντρική σελίδα Αναφορών."""
    template_name = 'leaves/reports_index.html'

    def dispatch(self, request, *args, **kwargs):
        _require_handler(request.user)
        return super().dispatch(request, *args, **kwargs)


@login_required
def department_managers_report(request):
    """Αναφορά προϊσταμένων ανά τμήμα — επισημαίνει τμήματα χωρίς προϊστάμενο."""
    _require_handler(request.user)

    departments = (
        Department.objects.select_related(
            'manager', 'department_type', 'parent_department', 'prefecture',
        )
        .order_by('name')
    )
    rows = []
    missing_count = 0
    for dept in departments:
        manager = dept.manager
        if not manager:
            missing_count += 1
        rows.append({
            'department': dept,
            'manager': manager,
            'has_manager': bool(manager),
        })

    return render(request, 'leaves/report_department_managers.html', {
        'rows': rows,
        'total_count': len(rows),
        'missing_count': missing_count,
        'with_manager_count': len(rows) - missing_count,
    })
