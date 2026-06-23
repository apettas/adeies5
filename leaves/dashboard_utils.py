"""
Dashboard utilities - sorting, filtering, action resolver
"""
from django.db.models import DateTimeField, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from leaves.models import LeaveRequest


def apply_sort(queryset, sort_param):
    """Εφαρμόζει ταξινόμηση, με Coalesce για submitted_at (fallback σε created_at)."""
    if not sort_param:
        return queryset

    field = sort_param.lstrip('-')
    if field == 'submitted_at':
        queryset = queryset.annotate(
            _submission_sort=Coalesce('submitted_at', 'created_at', output_field=DateTimeField())
        )
        if sort_param.startswith('-'):
            return queryset.order_by('-_submission_sort')
        return queryset.order_by('_submission_sort')

    return queryset.order_by(sort_param)


class RoleDashboardMixin:
    """Θυμάται τον τελευταίο ενεργό ρόλο dashboard στο session."""

    dashboard_role_key = None

    def dispatch(self, request, *args, **kwargs):
        if self.dashboard_role_key:
            request.session['active_dashboard_role'] = self.dashboard_role_key
        return super().dispatch(request, *args, **kwargs)


class DashboardFilterMixin:
    """Mixin for dashboard views with sorting and filtering support."""

    sortable_fields = []
    default_sort = '-created_at'

    def get_sort_params(self):
        """Get sorting parameters from request."""
        sort_field = self.request.GET.get('sort', self.default_sort.lstrip('-'))
        sort_dir = self.request.GET.get('dir', 'desc' if self.default_sort.startswith('-') else 'asc')

        if sort_field not in self.sortable_fields:
            sort_field = self.default_sort.lstrip('-')
            if sort_field:
                sort_dir = 'desc' if self.default_sort.startswith('-') else 'asc'

        if sort_dir == 'desc':
            sort_field = f'-{sort_field}'

        return sort_field

    def apply_filters(self, queryset):
        """Apply filters from request.GET."""
        leave_type = self.request.GET.get('leave_type')
        if leave_type:
            queryset = queryset.filter(leave_type_id=leave_type)

        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)

        year = self.request.GET.get('year')
        if year:
            try:
                year = int(year)
                queryset = queryset.filter(created_at__year=year)
            except (ValueError, TypeError):
                pass

        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(periods__start_date__gte=date_from)

        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(periods__end_date__lte=date_to)

        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.apply_filters(queryset)
        sort_param = self.get_sort_params()
        return apply_sort(queryset, sort_param)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context['current_sort'] = self.request.GET.get('sort', '')
        context['current_dir'] = self.request.GET.get('dir', '')
        context['current_leave_type'] = self.request.GET.get('leave_type', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_year'] = self.request.GET.get('year', '')
        context['current_date_from'] = self.request.GET.get('date_from', '')
        context['current_date_to'] = self.request.GET.get('date_to', '')

        from leaves.models import LeaveType
        context['leave_types'] = LeaveType.objects.filter(is_active=True)
        context['status_choices'] = self.model._meta.get_field('status').choices

        context['query_params'] = self.request.GET.copy()
        if 'page' in context['query_params']:
            del context['query_params']['page']

        return context


def _dedupe_actions(actions):
    """Κρατά την πρώτη εμφάνιση κάθε action code."""
    seen = set()
    unique = []
    for action in actions:
        code = action[0]
        if code in seen:
            continue
        seen.add(code)
        unique.append(action)
    return unique


def _append_view(actions):
    actions.append(('view', 'ΠΡΟΒΟΛΗ', 'leaves:leave_request_detail'))


def _owner_actions(leave_request, user, actions):
    if leave_request.user != user:
        return

    status = leave_request.status
    if status == 'DRAFT':
        _append_view(actions)
        actions.extend([
            ('edit', 'ΕΠΕΞΕΡΓΑΣΙΑ', None),
            ('submit', 'ΥΠΟΒΟΛΗ', None),
            ('delete', 'ΔΙΑΓΡΑΦΗ', 'leaves:delete_leave_request'),
        ])
    elif leave_request.can_be_withdrawn:
        _append_view(actions)
        actions.append(('cancel', 'ΑΝΑΚΛΗΣΗ', 'leaves:withdraw_leave_request'))
    elif status == 'WAITING_FOR_DOCUMENTS':
        _append_view(actions)
        actions.append(('upload_attachment', 'ΑΝΕΒΑΣΜΑ ΔΙΚ/ΚΩΝ', 'leaves:leave_request_detail'))
    elif status == 'COMPLETED':
        _append_view(actions)
        actions.append(('cancel_completed', 'ΑΝΑΚΛΗΣΗ ΟΛΟΚΛΗΡΩΜΕΝΗΣ', 'leaves:withdraw_completed_leave'))
    else:
        _append_view(actions)


def _handler_actions(leave_request, actions):
    status = leave_request.status

    if status == 'PENDING_PROTOCOL':
        _append_view(actions)
        actions.extend([
            ('protocol', 'ΚΑΤΑΧΩΡΗΣΗ ΠΡΩΤ.', None),
            ('send_protocol_pdf', 'ΑΠΟΣΤΟΛΗ PDF', 'leaves:send_to_protocol'),
            ('reject', 'ΑΠΟΡΡΙΨΗ', None),
        ])
    elif status == 'IN_REVIEW':
        _append_view(actions)
        actions.extend([
            ('request_documents', 'ΑΙΤΗΣΗ ΔΙΚ/ΚΩΝ', 'leaves:request_documents'),
            ('return', 'ΕΠΙΣΤΡΟΦΗ', None),
            ('reject', 'ΑΠΟΡΡΙΨΗ', None),
        ])
        if leave_request.can_send_to_yc:
            actions.append(('yc_referral', 'ΔΙΑΒΙΒΑΣΤΙΚΟ ΥΕ', 'leaves:send_to_yc_committee'))
        else:
            actions.append(('decision', 'ΕΤΟΙΜΑΣΙΑ ΑΠΟΦΑΣΗΣ', 'leaves:prepare_decision_preview'))
        actions.append(('complete', 'ΟΛΟΚΛΗΡΩΣΗ', 'leaves:complete_leave_request'))
    elif status == 'WAITING_FOR_DOCUMENTS':
        _append_view(actions)
        actions.extend([
            ('upload_docs', 'ΠΑΡΟΧΗ ΔΙΚ/ΚΩΝ', None),
            ('return', 'ΕΠΙΣΤΡΟΦΗ', None),
            ('reject', 'ΑΠΟΡΡΙΨΗ', None),
        ])
    elif status == 'PENDING_YC_COMMITTEE':
        _append_view(actions)
        actions.extend([
            ('upload_docs', 'ΑΠΟΦΑΣΗ ΥΕ', 'leaves:receive_from_yc_committee'),
            ('reject', 'ΑΠΟΡΡΙΨΗ', None),
        ])
    elif status == 'DECISION_PREPARATION':
        _append_view(actions)
        actions.append(('edit_decision', 'ΕΠΕΞΕΡΓΑΣΙΑ ΑΠΟΦΑΣΗΣ', 'leaves:prepare_decision_preview'))
        if leave_request.has_decision_pdf():
            actions.append(('send_signatures', 'ΠΡΟΣ ΥΠΟΓΡΑΦΕΣ', 'leaves:send_to_signatures'))
        actions.append(('reject', 'ΑΠΟΡΡΙΨΗ', None))
    elif status == 'PENDING_SIGNATURES':
        _append_view(actions)
        actions.append(('edit_decision', 'ΑΠΟΦΑΣΗ', 'leaves:prepare_decision_preview'))
        if leave_request.can_upload_exact_copy():
            actions.append(('upload_final', 'UPLOAD ΤΕΛΙΚΗΣ', None))
        if leave_request.can_complete_request():
            actions.append(('complete', 'ΟΛΟΚΛΗΡΩΣΗ', 'leaves:complete_leave_request_final'))
        actions.append(('reject', 'ΑΠΟΡΡΙΨΗ', None))
    elif status in ['COMPLETED', 'REJECTED_BY_LEAVES_DEPT', 'SUPERVISOR_REJECTED', 'CANCELLED_BY_APPLICANT']:
        _append_view(actions)
    else:
        _append_view(actions)


def _manager_actions(leave_request, user, actions):
    if leave_request.can_be_approved_by(user):
        _append_view(actions)
        actions.extend([
            ('approve', 'ΕΓΚΡΙΣΗ', None),
            ('reject', 'ΑΠΟΡΡΙΨΗ', None),
        ])
    elif leave_request.can_add_kedasy_kepea_protocol(user):
        _append_view(actions)
        actions.append(('kedasy_protocol', 'ΚΑΤΑΧΩΡΗΣΗ ΠΡΩΤ.', None))


def get_available_actions(leave_request, user):
    """
    Ενιαία λίστα ενεργειών ανά κατάσταση αίτησης και ρόλο χρήστη.
    Returns: [(action_code, label, url_name_or_None), ...]
    """
    if not leave_request or not user or not user.is_authenticated:
        return []

    actions = []

    _owner_actions(leave_request, user, actions)

    if user.is_leave_handler:
        _handler_actions(leave_request, actions)

    if user.is_department_manager or user.is_secretary:
        _manager_actions(leave_request, user, actions)

    return _dedupe_actions(actions)
