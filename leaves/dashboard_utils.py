"""
Dashboard utilities - sorting, filtering, action resolver
"""
from django.db.models import Q


class DashboardFilterMixin:
    """Mixin for dashboard views with sorting and filtering support."""

    # Fields that can be sorted
    sortable_fields = []
    default_sort = '-created_at'

    def get_sort_params(self):
        """Get sorting parameters from request."""
        sort_field = self.request.GET.get('sort', self.default_sort.lstrip('-'))
        sort_dir = self.request.GET.get('dir', 'desc' if self.default_sort.startswith('-') else 'asc')
        
        # Validate sort field
        if sort_field not in self.sortable_fields:
            sort_field = self.default_sort.lstrip('-')
            if sort_field:
                sort_dir = 'desc' if self.default_sort.startswith('-') else 'asc'
        
        if sort_dir == 'desc':
            sort_field = f'-{sort_field}'
        
        return sort_field

    def apply_filters(self, queryset):
        """Apply filters from request.GET."""
        # Leave type filter
        leave_type = self.request.GET.get('leave_type')
        if leave_type:
            queryset = queryset.filter(leave_type_id=leave_type)
        
        # Status filter
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Year filter
        year = self.request.GET.get('year')
        if year:
            try:
                year = int(year)
                queryset = queryset.filter(created_at__year=year)
            except (ValueError, TypeError):
                pass
        
        # Date range filter
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(start_date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(end_date__lte=date_to)
        
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = self.apply_filters(queryset)
        sort_param = self.get_sort_params()
        if sort_param:
            queryset = queryset.order_by(sort_param)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Current filter state
        context['current_sort'] = self.request.GET.get('sort', '')
        context['current_dir'] = self.request.GET.get('dir', '')
        context['current_leave_type'] = self.request.GET.get('leave_type', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['current_year'] = self.request.GET.get('year', '')
        context['current_date_from'] = self.request.GET.get('date_from', '')
        context['current_date_to'] = self.request.GET.get('date_to', '')
        
        # Filters for dropdowns
        from leaves.models import LeaveType
        context['leave_types'] = LeaveType.objects.filter(is_active=True)
        context['status_choices'] = self.model._meta.get_field('status').choices
        
        # Preserve query params for pagination
        context['query_params'] = self.request.GET.copy()
        if 'page' in context['query_params']:
            del context['query_params']['page']
        
        return context


def get_available_actions(leave_request, user):
    """
    Returns list of available actions based on status + role + permissions.
    Returns: [(action_code, label, url_name_or_None), ...]
    """
    actions = []
    
    if not leave_request:
        return actions
    
    status = leave_request.status
    is_owner = leave_request.user == user
    is_handler = user.is_leave_handler
    is_manager = user.is_department_manager
    is_admin = user.is_administrator
    
    # Owner actions
    if is_owner:
        if status == 'DRAFT':
            actions.append(('view', 'ΠΡΟΒΟΛΗ', f'leaves:leave_request_detail'))
            actions.append(('edit', 'ΕΠΕΞΕΡΓΑΣΙΑ', None))
            actions.append(('submit', 'ΥΠΟΒΟΛΗ', None))
        elif status in ['SUBMITTED', 'PENDING_PROTOCOL']:
            actions.append(('view', 'ΠΡΟΒΟΛΗ', f'leaves:leave_request_detail'))
            actions.append(('cancel', 'ΑΝΑΚΛΗΣΗ', f'leaves:withdraw_leave_request'))
        else:
            actions.append(('view', 'ΠΡΟΒΟΛΗ', f'leaves:leave_request_detail'))
    
    # Handler actions
    if is_handler:
        if status == 'PENDING_PROTOCOL':
            actions.append(('view', 'ΠΡΟΒΟΛΗ', f'leaves:leave_request_detail'))
            actions.append(('protocol', 'ΚΑΤΑΧΩΡΗΣΗ ΠΡΩΤ.', None))
            actions.append(('reject', 'ΑΠΟΡΡΙΨΗ', None))
        elif status == 'IN_REVIEW':
            actions.append(('view', 'ΠΡΟΒΟΛΗ', f'leaves:leave_request_detail'))
            actions.append(('documents', 'ΑΝΑΜΟΝΗ ΔΙΚ/ΚΩΝ', None))
            actions.append(('reject', 'ΑΠΟΡΡΙΨΗ', None))
            actions.append(('decision', 'ΕΤΟΙΜΑΣΙΑ ΑΠΟΦΑΣΗΣ', None))
        elif status == 'WAITING_FOR_DOCUMENTS':
            actions.append(('view', 'ΠΡΟΒΟΛΗ', f'leaves:leave_request_detail'))
            actions.append(('upload_docs', 'ΠΑΡΟΧΗ ΔΙΚ/ΚΩΝ', f'leaves:provide_documents'))
            actions.append(('return', 'ΕΠΙΣΤΡΟΦΗ', f'leaves:return_leave_to_employee'))
            actions.append(('reject', 'ΑΠΟΡΡΙΨΗ', None))
        elif status == 'DECISION_PREPARATION':
            actions.append(('view', 'ΠΡΟΒΟΛΗ', f'leaves:leave_request_detail'))
            actions.append(('edit_decision', 'ΕΠΕΞΕΡΓΑΣΙΑ', None))
            actions.append(('send_signatures', 'ΠΡΟΣ ΥΠΟΓΡΑΦΕΣ', None))
        elif status == 'PENDING_SIGNATURES':
            actions.append(('view', 'ΠΡΟΒΟΛΗ', f'leaves:leave_request_detail'))
            actions.append(('upload_final', 'UPLOAD ΤΕΛΙΚΗΣ', None))
            actions.append(('complete', 'ΟΛΟΚΛΗΡΩΣΗ', None))
        else:
            actions.append(('view', 'ΠΡΟΒΟΛΗ', f'leaves:leave_request_detail'))
    
    # Manager actions
    if is_manager and status == 'SUBMITTED':
        actions.append(('view', 'ΠΡΟΒΟΛΗ', f'leaves:leave_request_detail'))
        actions.append(('approve', 'ΕΓΚΡΙΣΗ', None))
        actions.append(('reject', 'ΑΠΟΡΡΙΨΗ', None))
    
    return actions
