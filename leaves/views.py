from django.http import HttpResponse, JsonResponse, Http404
from django.utils.http import content_disposition_header
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, DetailView
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.conf import settings
from datetime import timedelta
import os
import mimetypes
from .models import LeaveRequest, LeavePeriod, LeaveType, SecureFile
from .forms import LeaveRequestForm
from .crypto_utils import SecureFileHandler, FileAccessController
from .attachment_helpers import save_leave_request_attachments_from_request
from .dashboard_utils import DashboardFilterMixin, get_available_actions
from notifications.utils import create_notification
from django.contrib.auth import get_user_model

User = get_user_model()

LOCK_TIMEOUT_MINUTES = 30


class EmployeeDashboardView(LoginRequiredMixin, DashboardFilterMixin, ListView):
    """Dashboard αιτήσεων για τον υπάλληλο - όλες οι προσωπικές του αιτήσεις"""
    model = LeaveRequest
    template_name = 'leaves/employee_dashboard.html'
    context_object_name = 'leave_requests'
    paginate_by = 20
    sortable_fields = ['leave_type__name', 'status', 'submitted_at', 'id', 'protocol_number']
    default_sort = '-submitted_at'

    def get_queryset(self):
        queryset = LeaveRequest.objects.filter(user=self.request.user).select_related('leave_type')
        queryset = self.apply_filters(queryset)
        sort_param = self.get_sort_params()
        if sort_param:
            queryset = queryset.order_by(sort_param)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Add actions to each leave request
        for lr in context['leave_requests']:
            lr.actions = get_available_actions(lr, user)
        
        # Leave balance information
        context['leave_balance'] = user.leave_balance
        context['carryover_days'] = user.carryover_leave_days
        context['current_year_days'] = user.current_year_leave_balance
        context['annual_entitlement'] = user.annual_leave_entitlement
        context['current_regular_balance'] = user.current_regular_leave_balance
        
        # Ledger entries (last 5)
        from leaves.utils.balance_ledger import get_balance_entries
        context['recent_balance_entries'] = get_balance_entries(user)[:5]
        
        # Sick leave information
        context['sick_days_remaining'] = user.sick_leave_with_declaration
        context['sick_days_current_year'] = user.sick_days_current_year
        
        # Αναρρωτικές Άδειες με ΥΔ — χρήση τρέχοντος έτους
        from django.utils import timezone
        context['sick_leave_yd_used'] = LeaveRequest.objects.filter(
            user=user,
            leave_type__is_sick_leave_yd=True,
            status='COMPLETED',
            submitted_at__year=timezone.now().year
        ).count()
        context['sick_leave_yd_limit'] = user.sick_leave_with_declaration
        
        # Σύνολο Αναρρωτικών Αδειών τρέχοντος έτους (όχι μόνο completed — όλες εκτός draft/rejected)
        year = timezone.now().year
        sick_lrs = LeaveRequest.objects.filter(
            user=user,
            leave_type__is_sick_leave_total=True,
            submitted_at__year=year
        ).exclude(
            status__in=['DRAFT', 'SUPERVISOR_REJECTED', 'REJECTED_BY_LEAVES_DEPT', 'CANCELLED_BY_APPLICANT']
        ).prefetch_related('periods')
        sick_total = sum(lr.total_days for lr in sick_lrs)
        context['sick_total_days'] = sick_total
        context['sick_exceeds_threshold'] = sick_total > 8
        from leaves.models import YCCommitteeAcknowledgment
        context['sick_alert_acknowledged'] = YCCommitteeAcknowledgment.objects.filter(
            handler=user, employee=user
        ).exists() if sick_total > 8 else True
        
        # Στατιστικά
        all_requests = LeaveRequest.objects.filter(user=self.request.user)
        pending_documents_qs = all_requests.filter(status='WAITING_FOR_DOCUMENTS')
        context.update({
            'total_requests': all_requests.count(),
            'pending_documents_requests': pending_documents_qs.count(),
            'pending_documents_list': pending_documents_qs.select_related(
                'leave_type', 'documents_requested_by'
            ).order_by('-documents_requested_at'),
            'pending_requests': all_requests.filter(
                status__in=['SUBMITTED', 'PENDING_PROTOCOL', 'WAITING_FOR_DOCUMENTS', 'IN_REVIEW']
            ).count(),
            'completed_requests': all_requests.filter(status='COMPLETED').count(),
            'rejected_requests': all_requests.filter(
                status__in=['SUPERVISOR_REJECTED', 'REJECTED_BY_LEAVES_DEPT']
            ).count(),
            'can_request_leave': user.has_leave_request_permission(),
        })
        
        return context


class CreateLeaveRequestView(LoginRequiredMixin, CreateView):
    """Δημιουργία νέας αίτησης άδειας"""
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'leaves/create_leave_request.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Έλεγχος αν ο χρήστης μπορεί να αιτηθεί άδεια
        if not request.user.has_leave_request_permission():
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Δεν έχετε δικαίωμα υποβολής αιτήσεων άδειας.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['revocation_type_ids'] = list(
            LeaveType.objects.filter(is_revocation=True, is_active=True).values_list('id', flat=True)
        )
        return context

    def get_success_url(self):
        """Ανακατεύθυνση στο κατάλληλο dashboard ανάλογα με τον ρόλο"""
        user = self.request.user
        if user.is_leave_handler:
            return reverse_lazy('leaves:handler_dashboard')
        elif user.is_department_manager:
            return reverse_lazy('leaves:manager_dashboard')
        elif user.is_secretary:
            return reverse_lazy('leaves:secretary_dashboard')
        else:
            return reverse_lazy('leaves:employee_dashboard')
    
    def form_valid(self, form):
        # Αποθηκεύουμε την αίτηση ΧΩΡΙΣ τα αρχεία προσωρινά για να έχουμε ID
        leave_request = LeaveRequest(
            user=self.request.user,
            leave_type=form.cleaned_data['leave_type'],
            description=form.cleaned_data['description'],
            days=form.cleaned_data.get('days', 1),
            status='DRAFT'  # Προσωρινή κατάσταση
        )
        leave_request.save()
        
        # Δημιουργία periods
        periods = []
        total_days = 0
        periods_data = form.cleaned_data.get('periods_data', [])
        for period_data in periods_data:
            period = LeavePeriod(
                leave_request=leave_request,
                start_date=period_data['start_date'],
                end_date=period_data['end_date']
            )
            period.save()
            periods.append({
                'start_date': period_data['start_date'],
                'end_date': period_data['end_date'],
                'days': period_data['days']
            })
            total_days += period_data['days']
        
        # Αποθήκευση αρχείων αμέσως
        attachments = []
        from .crypto_utils import SecureFileHandler
        from django.conf import settings
        import os
        from django.utils import timezone
        
        private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                                   os.path.join(settings.BASE_DIR, 'private_media'))
        
        for key in self.request.FILES.keys():
            if key.startswith('attachment_'):
                file_obj = self.request.FILES[key]
                index = key.replace('attachment_', '')
                description_key = f'attachment_description_{index}'
                description = self.request.POST.get(description_key, '')
                if file_obj:
                    try:
                        # Επικύρωση αρχείου πριν την αποθήκευση
                        is_valid, error_message = SecureFileHandler.validate_file(file_obj)
                        if not is_valid:
                            # Διαγραφή του αιτήματος αν υπάρχει σφάλμα
                            leave_request.delete()
                            form.add_error(None, f'Αρχείο "{file_obj.name}": {error_message}')
                            return self.form_invalid(form)
                        
                        file_path = os.path.join(
                            private_media_root,
                            'leave_requests',
                            str(leave_request.id),
                            f"{timezone.now().strftime('%Y%m%d_%H%M%S')}_{file_obj.name}"
                        )
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        success, key_hex, file_size = SecureFileHandler.save_encrypted_file(file_obj, file_path)
                        
                        if success:
                            attachment = SecureFile.objects.create(
                                leave_request=leave_request,
                                original_filename=file_obj.name,
                                file_path=file_path,
                                file_size=file_size,
                                content_type=file_obj.content_type,
                                encryption_key=key_hex,
                                uploaded_by=self.request.user,
                                description=description if description else f"Συνημμένο {index}"
                            )
                            attachments.append({
                                'file_name': file_obj.name,
                                'description': description if description else f"Συνημμένο {index}"
                            })
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Error handling file upload {file_obj.name}: {str(e)}")
        
        # Παίρνουμε τα attachments από τη βάση δεδομένων μετά την αποθήκευση
        leave_request.refresh_from_db()
        saved_attachments = leave_request.attachments.all()
        
        context = {
            'form_data': form.cleaned_data,
            'user': self.request.user,
            'leave_request': leave_request,  # Προσθήκη leave_request στο context
            'periods': periods,
            'total_days': total_days,
            'attachments': saved_attachments  # Χρήση των αποθηκευμένων attachments
        }
        return render(self.request, 'leaves/preview_request.html', context)
    
    def _handle_file_uploads(self, form):
        """Επεξεργασία και κρυπτογραφημένη αποθήκευση πολλαπλών αρχείων"""
        private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                                   os.path.join(settings.BASE_DIR, 'private_media'))
        
        # Process multiple file uploads
        for key in self.request.FILES.keys():
            if key.startswith('attachment_'):
                file_obj = self.request.FILES[key]
                index = key.replace('attachment_', '')
                description_key = f'attachment_description_{index}'
                description = self.request.POST.get(description_key, '')
                
                if not file_obj:
                    continue
                
                # Επικύρωση αρχείου πριν την αποθήκευση
                is_valid, error_message = SecureFileHandler.validate_file(file_obj)
                if not is_valid:
                    messages.error(self.request, f'Αρχείο "{file_obj.name}": {error_message}')
                    continue
                
                try:
                    # Δημιουργία unique file path
                    file_path = os.path.join(
                        private_media_root,
                        'leave_requests',
                        str(self.object.id),
                        f"{timezone.now().strftime('%Y%m%d_%H%M%S')}_{file_obj.name}"
                    )
                    
                    # Ensure directory exists
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    
                    # Κρυπτογραφημένη αποθήκευση
                    success, key_hex, file_size = SecureFileHandler.save_encrypted_file(
                        file_obj, file_path
                    )
                    
                    if success:
                        # Δημιουργία SecureFile record
                        SecureFile.objects.create(
                            leave_request=self.object,
                            original_filename=file_obj.name,
                            file_path=file_path,
                            file_size=file_size,
                            content_type=file_obj.content_type,
                            encryption_key=key_hex,
                            uploaded_by=self.request.user,
                            description=description if description else f"Συνημμένο {index}"
                        )
                        messages.success(
                            self.request,
                            f'Επιτυχής αποθήκευση αρχείου "{file_obj.name}".'
                        )
                    else:
                        messages.warning(
                            self.request,
                            f'Αποτυχία αποθήκευσης αρχείου "{file_obj.name}".'
                        )
                        
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Error handling file upload {file_obj.name}: {str(e)}")
                    messages.error(
                        self.request,
                        f'Σφάλμα κατά την αποθήκευση του αρχείου "{file_obj.name}".'
                    )


class CreateAtypicalLeaveView(LoginRequiredMixin, CreateView):
    """Δημιουργία άτυπης άδειας (is_simple=True) — χωρίς PDF"""
    model = LeaveRequest
    template_name = 'leaves/create_leave_request.html'
    form_class = None  # Set in dispatch

    def dispatch(self, request, *args, **kwargs):
        if not request.user.department or not request.user.department.has_atypical_leaves:
            raise PermissionDenied("Δεν έχετε δικαίωμα δημιουργίας άτυπης άδειας.")
        from .forms import AtypicalLeaveForm
        self.form_class = AtypicalLeaveForm
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        from django.urls import reverse_lazy
        if self.request.user.is_department_manager:
            return reverse_lazy('leaves:manager_dashboard')
        return reverse_lazy('leaves:employee_dashboard')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_atypical'] = True
        context['revocation_type_ids'] = list(
            LeaveType.objects.filter(is_revocation=True, is_active=True).values_list('id', flat=True)
        )
        return context

    def form_valid(self, form):
        leave_request = LeaveRequest(
            user=self.request.user,
            leave_type=form.cleaned_data['leave_type'],
            description=form.cleaned_data['description'],
            days=form.cleaned_data.get('days', 1),
            requested_days=form.cleaned_data.get('days', 1),
            status='DRAFT'  # Προσωρινή κατάσταση
        )
        leave_request.save()
        periods_data = form.cleaned_data.get('periods_data', [])
        for period_data in periods_data:
            LeavePeriod.objects.create(
                leave_request=leave_request,
                start_date=period_data['start_date'],
                end_date=period_data['end_date']
            )
        from leaves.attachment_helpers import save_leave_request_attachments_from_request
        save_leave_request_attachments_from_request(self.request, leave_request, self.request.user)
        try:
            leave_request.submit()
        except ValueError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)
        messages.success(self.request, 'Η άτυπη άδεια υποβλήθηκε επιτυχώς.')
        return redirect(self.get_success_url())


@login_required
def create_leave_for_user(request, user_id):
    """Ο χειριστής δημιουργεί νέα αίτηση άδειας για άλλον χρήστη"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Μόνο χειριστές αδειών μπορούν να δημιουργήσουν άδεια για άλλον χρήστη.")
    target_user = get_object_or_404(get_user_model(), pk=user_id)

    from .forms import LeaveRequestForm
    if request.method == 'POST':
        form = LeaveRequestForm(request.POST, request.FILES)
        if form.is_valid():
            leave_request = LeaveRequest(
                user=target_user,
                leave_type=form.cleaned_data['leave_type'],
                description=form.cleaned_data['description'],
                days=form.cleaned_data.get('days', 1),
                requested_days=form.cleaned_data.get('days', 1),
                status='DRAFT'
            )
            leave_request.save()
            periods_data = form.cleaned_data.get('periods_data', [])
            for period_data in periods_data:
                LeavePeriod.objects.create(
                    leave_request=leave_request,
                    start_date=period_data['start_date'],
                    end_date=period_data['end_date']
                )
            private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                                        os.path.join(settings.BASE_DIR, 'private_media'))
            for key in request.FILES.keys():
                if key.startswith('attachment_'):
                    file_obj = request.FILES[key]
                    index = key.replace('attachment_', '')
                    description_key = f'attachment_description_{index}'
                    description = request.POST.get(description_key, '')
                    if file_obj:
                        import uuid
                        ext = file_obj.name.split('.')[-1]
                        fname = f"{uuid.uuid4().hex}.{ext}"
                        file_path = os.path.join(private_media_root, 'leave_requests', str(leave_request.id), fname)
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        success, key_hex, file_size = SecureFileHandler.save_encrypted_file(file_obj, file_path)
                        if success:
                            SecureFile.objects.create(
                                leave_request=leave_request,
                                original_filename=file_obj.name,
                                file_path=file_path,
                                file_size=file_size,
                                content_type=file_obj.content_type or '',
                                encryption_key=key_hex,
                                uploaded_by=request.user,
                                description=description,
                            )
            try:
                leave_request.submit()
                from django.template.loader import render_to_string
                from weasyprint import HTML
                private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                                            os.path.join(settings.BASE_DIR, 'private_media'))
                pdf_path = os.path.join(private_media_root, 'leave_requests', str(leave_request.id), 'request.pdf')
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                leave_request.refresh_from_db()
                pdf_context = {
                    'leave_request': leave_request,
                    'user': request.user,
                    'periods': leave_request.periods.all(),
                    'request_text': leave_request.description or '',
                    'attachments': leave_request.attachments.all(),
                    'form_data': {'description': leave_request.description, 'leave_type': leave_request.leave_type},
                }
                html_content = render_to_string('leaves/pdf_template.html', pdf_context)
                HTML(string=html_content).write_pdf(pdf_path)
                next_status = 'ΥΠΟΒΛΗΘΕΙΣΑ' if leave_request.status == 'SUBMITTED' else 'ΓΙΑ ΠΡΩΤΟΚΟΛΛΟ ΠΔΕΔΕ'
                messages.success(request, f'Η αίτηση δημιουργήθηκε και υποβλήθηκε για τον/την {target_user.full_name}. Κατάσταση: {next_status}.')
            except ValueError as e:
                messages.warning(request, f'Η αίτηση δημιουργήθηκε αλλά δεν υποβλήθηκε: {e}')
            return redirect('leaves:handler_dashboard')
    else:
        form = LeaveRequestForm()

    return render(request, 'leaves/create_leave_request.html', {
        'form': form,
        'target_user': target_user,
        'handler_creating': True,
        'revocation_type_ids': list(
            LeaveType.objects.filter(is_revocation=True, is_active=True).values_list('id', flat=True)
        ),
    })


class ManagerDashboardView(LoginRequiredMixin, ListView):
    """Dashboard για Προϊστάμενο - Αιτήσεις προς έγκριση"""
    model = LeaveRequest
    template_name = 'leaves/manager_dashboard.html'
    context_object_name = 'leave_requests'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_department_manager:
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Αιτήσεις των υφισταμένων που περιμένουν έγκριση
        subordinates = self.request.user.get_subordinates()
        employees_to_include = list(subordinates)
        
        # Αν ο χρήστης είναι ο ανώτερος προϊστάμενος, προσθέτουμε και αιτήσεις
        # από άλλους προϊσταμένους/χειριστές που δεν έχουν manager
        if self.request.user.is_department_manager:
            from accounts.models import User
            # Προσθήκη άλλων managers/handlers του ίδιου τμήματος
            other_department_users = User.objects.filter(
                Q(roles__code='MANAGER') | Q(roles__code='HR_OFFICER'),
                department=self.request.user.department
            ).exclude(pk=self.request.user.pk).distinct()
            
            employees_to_include.extend(list(other_department_users))
        
        # Δημιουργία query conditions - μόνο για αιτήσεις που χρειάζονται έγκριση
        query_conditions = Q(
            user__in=employees_to_include,
            status='SUBMITTED'
        )
        
        # Προσθήκη αιτήσεων από managers που χρειάζονται ιεραρχική έγκριση
        # Για τον delegkos (PDEDE manager), προσθέτουμε αιτήσεις από την kizilou (AUTOTELOUS_DN manager)
        if (self.request.user.department and
            self.request.user.department.code == 'PDEDE' and
            self.request.user.is_department_manager):
            
            # Αιτήσεις από AUTOTELOUS_DN manager που χρειάζονται έγκριση από PDEDE manager
            autotelous_hierarchy_condition = Q(
                user__department__code='AUTOTELOUS_DN',
                user__roles__code='MANAGER',
                status='SUBMITTED'
            )
            
            # Ενώνουμε τα κριτήρια με OR
            query_conditions = query_conditions | autotelous_hierarchy_condition
        
        # Αν είναι προϊστάμενος ΚΕΔΑΣΥ, προσθέτουμε και αιτήσεις από ΣΔΕΥ που ανήκουν σε αυτό
        # αλλά ΜΟΝΟ αυτές που είναι σε status SUBMITTED (χρειάζονται έγκριση)
        if (self.request.user.department and
            self.request.user.department.department_type and
            self.request.user.department.department_type.code == 'KEDASY'):
            
            # Προσθήκη αιτήσεων από ΣΔΕΥ που έχουν το ΚΕΔΑΣΥ ως parent
            # αλλά μόνο αυτές που είναι SUBMITTED (χρειάζονται έγκριση)
            sdei_condition = Q(
                user__department__department_type__code='SDEY',
                user__department__parent_department=self.request.user.department,
                status='SUBMITTED'
            )
            
            # Ενώνουμε τα κριτήρια με OR
            query_conditions = query_conditions | sdei_condition
        
        return LeaveRequest.objects.filter(query_conditions).select_related('user', 'leave_type').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subordinates = self.request.user.get_subordinates()
        
        # Βασικά στατιστικά
        context.update({
            'pending_approvals': self.get_queryset().count(),
            'total_subordinates': subordinates.count(),
            'approved_this_month': LeaveRequest.objects.filter(
                user__in=subordinates,
                status='PENDING_PROTOCOL',
                manager_approved_at__month=timezone.now().month
            ).count(),
            'today': timezone.now().date(),
        })

        # Sick days alert - υπάλληλοι με >8 αναρρωτικές ημέρες τρέχοντος έτους
        from accounts.models import User
        context['sick_days_alert_users'] = User.objects.filter(
            id__in=subordinates.values_list('id', flat=True),
            sick_days_current_year__gt=8
        ).select_related('department')

        # Οικιακές αιτήσεις του manager
        context['my_leave_requests'] = LeaveRequest.objects.filter(
            user=self.request.user
        ).select_related('leave_type').order_by('-created_at')[:10]

        # Υπόλοιπο αδειών του manager
        context['my_leave_balance'] = self.request.user.leave_balance
        context['my_current_year_days'] = self.request.user.current_year_leave_balance
        context['my_carryover_days'] = self.request.user.carryover_leave_days
        context['my_annual_entitlement'] = self.request.user.annual_leave_entitlement
        
        # Στατιστικά για ΚΕΔΑΣΥ/ΚΕΠΕΑ αν ο προϊστάμενος ανήκει σε τέτοιο τμήμα
        if (self.request.user.department and
            self.request.user.department.department_type and
            self.request.user.department.department_type.code in ['KEDASY', 'KEPEA']):
            
            # Φίλτρο για το τμήμα του προϊσταμένου
            department_filter = Q(user__department=self.request.user.department)
            
            # Αν είναι ΚΕΔΑΣΥ, προσθέτουμε και ΣΔΕΥ τμήματα
            if self.request.user.department.department_type.code == 'KEDASY':
                sdei_filter = Q(
                    user__department__department_type__code='SDEY',
                    user__department__parent_department=self.request.user.department
                )
                department_filter = department_filter | sdei_filter
            
            context.update({
                'is_kedasy_kepea_manager': True,
                'kedasy_kepea_pending_protocol_count': LeaveRequest.objects.filter(
                    status='PENDING_KEDASY_PROTOCOL'
                ).filter(department_filter).count(),
                'kedasy_kepea_completed_this_month': LeaveRequest.objects.filter(
                    kedasy_kepea_protocol_date__month=timezone.now().month,
                    kedasy_kepea_protocol_number__isnull=False
                ).filter(department_filter).count(),
                'kedasy_kepea_total_processed': LeaveRequest.objects.filter(
                    kedasy_kepea_protocol_number__isnull=False
                ).filter(department_filter).count(),
            })
            
            # Πρόσφατα πρωτοκολλημένες αιτήσεις (τελευταίες 10)
            recent_kedasy_kepea_processed = LeaveRequest.objects.filter(
                kedasy_kepea_protocol_number__isnull=False
            ).filter(department_filter).select_related('user', 'leave_type', 'kedasy_kepea_protocol_by').order_by('-kedasy_kepea_protocol_date')[:10]
            
            context['kedasy_kepea_recent_processed'] = recent_kedasy_kepea_processed
            
            # Αιτήσεις ΚΕΔΑΣΥ/ΚΕΠΕΑ που περιμένουν πρωτόκολλο ΚΕΔΑΣΥ
            kedasy_kepea_pending_requests = LeaveRequest.objects.filter(
                status='PENDING_KEDASY_PROTOCOL'
            ).filter(department_filter).select_related('user', 'user__department', 'user__department__department_type', 'leave_type').order_by('-submitted_at')
            
            context['kedasy_kepea_pending_requests'] = kedasy_kepea_pending_requests
            
            # Αν είναι ΚΕΔΑΣΥ προϊστάμενος, προσθέτουμε τη λίστα ΣΔΕΥ χρηστών
            if self.request.user.department.department_type.code == 'KEDASY':
                from accounts.models import User
                sdeu_users = User.objects.filter(
                    department__department_type__code='SDEY',
                    department__parent_department=self.request.user.department,
                    is_active=True
                ).select_related('department').order_by('last_name', 'first_name')
                
                context['sdeu_users'] = sdeu_users
                context['sdeu_users_count'] = sdeu_users.count()
        
        return context


@login_required
def approve_leave_request(request, pk):
    """Έγκριση αίτησης από προϊστάμενο ή υπεύθυνο προσωπικού"""
    if not request.user.can_approve_leaves():
        raise PermissionDenied("Δεν έχετε δικαίωμα έγκρισης.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος δικαιωμάτων έγκρισης
    can_approve = False
    
    if request.user.is_leave_handler:
        # Υπεύθυνοι προσωπικού μπορούν να εγκρίνουν όλες τις αιτήσεις
        can_approve = True
    elif request.user.is_department_manager:
        # Νέα λογική: Έλεγχος αν ο χρήστης είναι ο σωστός προϊστάμενος για έγκριση
        approving_manager = leave_request.user.get_approving_manager()
        if approving_manager == request.user:
            can_approve = True
        
        # Διατήρηση της υπάρχουσας λογικής για ΚΕΔΑΣΥ/ΣΔΕΥ
        if (not can_approve and
            request.user.department and request.user.department.department_type and
            request.user.department.department_type.code == 'KEDASY' and
            leave_request.user.department and leave_request.user.department.department_type and
            leave_request.user.department.department_type.code == 'SDEY' and
            leave_request.user.department.parent_department == request.user.department):
            can_approve = True
        
        # Διατήρηση της υπάρχουσας λογικής για το ίδιο τμήμα (για συμβατότητα)
        if not can_approve and request.user.department and leave_request.user.department:
            can_approve = (request.user.department.id == leave_request.user.department.id)
    
    if not can_approve:
        raise PermissionDenied("Δεν μπορείτε να εγκρίνετε αυτή την αίτηση.")
    
    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        kedasy_protocol_number = request.POST.get('kedasy_protocol_number', '').strip()
        kedasy_protocol_date = request.POST.get('kedasy_protocol_date', '')
        
        try:
            # Έγκριση από προϊστάμενο
            leave_request.approve_by_manager(request.user, comments)
            
            # Αν η αίτηση είναι από ΚΕΔΑΣΥ/ΚΕΠΕΑ και δόθηκε πρωτόκολλο, το προσθέτουμε
            if leave_request.is_kedasy_kepea_department() and kedasy_protocol_number:
                # Μετατροπή ημερομηνίας αν δόθηκε
                protocol_date_obj = timezone.now().date()
                if kedasy_protocol_date:
                    from datetime import datetime
                    protocol_date_obj = datetime.strptime(kedasy_protocol_date, '%Y-%m-%d').date()
                
                # Προσθήκη πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ
                leave_request.add_kedasy_kepea_protocol(
                    protocol_number=kedasy_protocol_number,
                    protocol_date=protocol_date_obj,
                    user=request.user
                )
                messages.success(request, f'Η αίτηση εγκρίθηκε και πρωτοκολλήθηκε με αρ. {kedasy_protocol_number}!')
            else:
                messages.success(request, 'Η αίτηση εγκρίθηκε επιτυχώς!')
            
            # Αναγέννηση PDF με την υπογραφή του προϊσταμένου
            try:
                from django.template.loader import render_to_string
                from weasyprint import HTML
                import os
                from django.conf import settings
                private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                                            os.path.join(settings.BASE_DIR, 'private_media'))
                leave_request.refresh_from_db()
                pdf_path = os.path.join(private_media_root, 'leave_requests', str(leave_request.id), 'request.pdf')
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                pdf_context = {
                    'leave_request': leave_request,
                    'user': leave_request.user,
                    'periods': leave_request.periods.all(),
                    'request_text': leave_request.description or '',
                    'attachments': leave_request.attachments.all(),
                    'form_data': {'description': leave_request.description, 'leave_type': leave_request.leave_type},
                }
                html_content = render_to_string('leaves/pdf_template.html', pdf_context)
                HTML(string=html_content).write_pdf(pdf_path)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error regenerating PDF after manager approval: {str(e)}")
            
            # Ειδοποίηση στους χειριστές αδειών
            from accounts.models import User
            leave_handlers = User.objects.filter(roles__code='LEAVE_HANDLER', is_active=True).distinct()
            for handler in leave_handlers:
                create_notification(
                    user=handler,
                    title="Αίτηση Εγκρίθηκε από Προϊστάμενο",
                    message=f"Η αίτηση του/της {leave_request.user.full_name} εγκρίθηκε και περιμένει επεξεργασία",
                    related_object=leave_request
                )
            
            # Ειδοποίηση στον υπάλληλο
            create_notification(
                user=leave_request.user,
                title="Αίτηση Εγκρίθηκε",
                message=f"Η αίτησή σας για {leave_request.leave_type.name} εγκρίθηκε από τον προϊστάμενό σας",
                related_object=leave_request
            )
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την έγκριση: {str(e)}')
    
    return redirect('leaves:leave_request_detail', pk=pk)


@login_required
def reject_leave_request(request, pk):
    """Απόρριψη αίτησης από προϊστάμενο"""
    if not request.user.is_department_manager:
        raise PermissionDenied("Δεν έχετε δικαίωμα απόρριψης.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος αν ο χρήστης είναι ο προϊστάμενος του αιτούντα
    can_reject = False
    
    # Νέα λογική: Έλεγχος αν ο χρήστης είναι ο σωστός προϊστάμενος για απόρριψη
    approving_manager = leave_request.user.get_approving_manager()
    if approving_manager == request.user:
        can_reject = True
    
    # Διατήρηση της υπάρχουσας λογικής για συμβατότητα
    # Έλεγχος αν είναι ο άμεσος προϊστάμενος
    if not can_reject and leave_request.user.manager == request.user:
        can_reject = True
    
    # Έλεγχος αν είναι προϊστάμενος ΚΕΔΑΣΥ και η αίτηση από ΣΔΕΥ
    elif (not can_reject and request.user.department and request.user.department.department_type and
          request.user.department.department_type.code == 'KEDASY' and
          leave_request.user.department and leave_request.user.department.department_type and
          leave_request.user.department.department_type.code == 'SDEY' and
          leave_request.user.department.parent_department == request.user.department):
        can_reject = True
    
    if not can_reject:
        raise PermissionDenied("Δεν μπορείτε να απορρίψετε αυτή την αίτηση.")
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        try:
            leave_request.reject_by_manager(request.user, reason)
            
            # Ειδοποίηση στον υπάλληλο
            create_notification(
                user=leave_request.user,
                title="Αίτηση Απορρίφθηκε",
                message=f"Η αίτησή σας για {leave_request.leave_type.name} απορρίφθηκε από τον προϊστάμενό σας",
                related_object=leave_request
            )
            
            messages.success(request, 'Η αίτηση απορρίφθηκε επιτυχώς!')
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την απόρριψη: {str(e)}')
    
    return redirect('leaves:leave_request_detail', pk=pk)


class HandlerDashboardView(LoginRequiredMixin, DashboardFilterMixin, ListView):
    """Dashboard για Χειριστή Αδειών - Επεξεργασία αιτήσεων"""
    model = LeaveRequest
    template_name = 'leaves/handler_dashboard.html'
    context_object_name = 'leave_requests'
    paginate_by = 20
    sortable_fields = ['leave_type__name', 'protocol_number', 'status', 'submitted_at', 'id']
    default_sort = '-submitted_at'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_leave_handler:
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = LeaveRequest.objects.filter(
            status__in=['PENDING_PROTOCOL', 'WAITING_FOR_DOCUMENTS', 'IN_REVIEW', 'DECISION_PREPARATION', 'PENDING_YC_COMMITTEE', 'PENDING_SIGNATURES', 'COMPLETED', 'REJECTED_BY_LEAVES_DEPT']
        ).select_related('user', 'leave_type', 'manager_approved_by', 'locking_user')
        
        # Filter by active tab
        tab = self.request.GET.get('tab', 'all')
        tab_filters = {
            'all': ['PENDING_PROTOCOL', 'WAITING_FOR_DOCUMENTS', 'IN_REVIEW', 'DECISION_PREPARATION', 'PENDING_YC_COMMITTEE', 'PENDING_SIGNATURES', 'COMPLETED', 'REJECTED_BY_LEAVES_DEPT'],
            'protocol': ['PENDING_PROTOCOL'],
            'processing': ['IN_REVIEW'],
            'documents': ['WAITING_FOR_DOCUMENTS'],
            'decision': ['DECISION_PREPARATION'],
            'yc_committee': ['PENDING_YC_COMMITTEE'],
            'signatures': ['PENDING_SIGNATURES'],
            'completed': ['COMPLETED'],
            'rejected': ['REJECTED_BY_LEAVES_DEPT'],
        }
        if tab in tab_filters:
            queryset = LeaveRequest.objects.filter(
                status__in=tab_filters[tab]
            ).select_related('user', 'leave_type', 'manager_approved_by', 'locking_user')
        
        queryset = self.apply_filters(queryset)
        sort_param = self.get_sort_params()
        if sort_param:
            queryset = queryset.order_by(sort_param)
        
        # Clean up expired locks
        cutoff_time = timezone.now() - timedelta(minutes=LOCK_TIMEOUT_MINUTES)
        LeaveRequest.objects.filter(locked_at__lt=cutoff_time).update(locking_user=None, locked_at=None)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add actions to each leave request
        for lr in context['leave_requests']:
            lr.actions = get_available_actions(lr, self.request.user)
        
        # Active tab
        context['active_tab'] = self.request.GET.get('tab', 'all')
        
        # Tab counts
        all_active = LeaveRequest.objects.filter(
            status__in=['PENDING_PROTOCOL', 'WAITING_FOR_DOCUMENTS', 'IN_REVIEW', 'DECISION_PREPARATION', 'PENDING_YC_COMMITTEE', 'PENDING_SIGNATURES', 'COMPLETED', 'REJECTED_BY_LEAVES_DEPT']
        )
        context['tab_counts'] = {
            'all': all_active.count(),
            'protocol': LeaveRequest.objects.filter(status='PENDING_PROTOCOL').count(),
            'processing': LeaveRequest.objects.filter(status='IN_REVIEW').count(),
            'documents': LeaveRequest.objects.filter(status='WAITING_FOR_DOCUMENTS').count(),
            'decision': LeaveRequest.objects.filter(status='DECISION_PREPARATION').count(),
            'signatures': LeaveRequest.objects.filter(status='PENDING_SIGNATURES').count(),
            'completed': LeaveRequest.objects.filter(status='COMPLETED').count(),
            'rejected': LeaveRequest.objects.filter(status='REJECTED_BY_LEAVES_DEPT').count(),
            'yc_committee': LeaveRequest.objects.filter(status='PENDING_YC_COMMITTEE').count(),
        }
        

        
        # Υπόλοιπο Κανονικών Αδειών του χειριστή
        handler_user = self.request.user
        context['handler_leave_balance'] = handler_user.leave_balance
        context['handler_carryover_days'] = handler_user.carryover_leave_days
        context['handler_current_year_days'] = handler_user.current_year_leave_balance
        context['handler_annual_entitlement'] = handler_user.annual_leave_entitlement
        context['handler_regular_balance'] = handler_user.current_regular_leave_balance
        
        # Αιτήσεις για Πρωτόκολλο ΠΔΕΔΕ (όλες, για τα modals)
        context['pdede_pending_requests'] = LeaveRequest.objects.filter(
            status='PENDING_PROTOCOL'
        ).select_related('user', 'user__department', 'leave_type').order_by('-submitted_at')
        
        # Alert για Υγειονομική Επιτροπή — χρήστες > 8 αναρρωτικές ημέρες (Python-level calculation)
        from accounts.models import User
        from leaves.models import YCCommitteeAcknowledgment
        from django.utils import timezone
        acknowledged = YCCommitteeAcknowledgment.objects.filter(
            handler=self.request.user
        ).values_list('employee_id', flat=True)
        year = timezone.now().year
        sick_lrs = LeaveRequest.objects.filter(
            leave_type__is_sick_leave_total=True,
            submitted_at__year=year
        ).exclude(
            status__in=['DRAFT', 'SUPERVISOR_REJECTED', 'REJECTED_BY_LEAVES_DEPT', 'CANCELLED_BY_APPLICANT']
        ).select_related('user').prefetch_related('periods')
        user_totals = {}
        for lr in sick_lrs:
            uid = lr.user_id
            user_totals[uid] = user_totals.get(uid, 0) + lr.total_days
        alert_user_ids = [uid for uid, total in user_totals.items() if total > 8 and uid not in acknowledged]
        context['sick_alert_users'] = User.objects.filter(
            id__in=alert_user_ids,
            is_active=True
        ).select_related('department').order_by('last_name')
        context['sick_alert_count'] = context['sick_alert_users'].count()
        
        return context


class UsersListView(LoginRequiredMixin, ListView):
    """Λίστα χρηστών για χειριστή αδειών ή προϊστάμενο"""
    model = User
    template_name = 'leaves/users_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_leave_handler or request.user.is_department_manager):
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        view_mode = self.request.GET.get('view', 'department')
        q = self.request.GET.get('q', '').strip()
        
        def apply_search(qs):
            if q:
                qs = qs.filter(
                    Q(first_name__icontains=q) |
                    Q(last_name__icontains=q) |
                    Q(email__icontains=q) |
                    Q(department__name__icontains=q)
                )
            return qs
        
        if self.request.user.is_department_manager and view_mode == 'department':
            qs = self.request.user.get_subordinates().select_related('department').order_by('last_name', 'first_name')
        elif self.request.user.is_leave_handler and view_mode == 'handler':
            qs = User.objects.select_related('department').order_by('last_name', 'first_name')
        elif self.request.user.is_department_manager:
            qs = self.request.user.get_subordinates().select_related('department').order_by('last_name', 'first_name')
        elif self.request.user.is_leave_handler:
            qs = User.objects.select_related('department').order_by('last_name', 'first_name')
        else:
            return User.objects.none()
        
        return apply_search(qs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        view_mode = self.request.GET.get('view', 'department')
        search_query = self.request.GET.get('q', '')
        context['search_query'] = search_query
        
        # Στατιστικά ανάλογα με τον ρόλο και το view mode
        if self.request.user.is_department_manager and view_mode == 'department':
            # Στατιστικά για τους subordinates του προϊσταμένου
            subordinates = self.request.user.get_subordinates()
            
            context.update({
                'total_users': subordinates.count(),
                'active_users': subordinates.filter(is_active=True).count(),
                'employees': subordinates.filter(roles__code='EMPLOYEE').distinct().count(),
                'managers': subordinates.filter(roles__code='MANAGER').distinct().count(),
                'user_role': 'manager',
                'department_name': self.request.user.department.name if self.request.user.department else 'Άγνωστο',
                'view_mode': 'department'
            })
        elif self.request.user.is_leave_handler and view_mode == 'handler':
            # Στατιστικά για όλους τους χρήστες
            context.update({
                'total_users': User.objects.count(),
                'active_users': User.objects.filter(is_active=True).count(),
                'employees': User.objects.filter(roles__code='EMPLOYEE').distinct().count(),
                'managers': User.objects.filter(roles__code='MANAGER').distinct().count(),
                'user_role': 'handler',
                'view_mode': 'handler'
            })
        elif self.request.user.is_department_manager:
            # Default για department manager
            subordinates = self.request.user.get_subordinates()
            
            context.update({
                'total_users': subordinates.count(),
                'active_users': subordinates.filter(is_active=True).count(),
                'employees': subordinates.filter(roles__code='EMPLOYEE').distinct().count(),
                'managers': subordinates.filter(roles__code='MANAGER').distinct().count(),
                'user_role': 'manager',
                'department_name': self.request.user.department.name if self.request.user.department else 'Άγνωστο',
                'view_mode': 'department'
            })
        elif self.request.user.is_leave_handler:
            # Default για leave handler
            context.update({
                'total_users': User.objects.count(),
                'active_users': User.objects.filter(is_active=True).count(),
                'employees': User.objects.filter(roles__code='EMPLOYEE').distinct().count(),
                'managers': User.objects.filter(roles__code='MANAGER').distinct().count(),
                'user_role': 'handler',
                'view_mode': 'handler'
            })
        
        # Προσθήκη πληροφοριών για dual-role users
        context.update({
            'has_dual_role': self.request.user.is_department_manager and self.request.user.is_leave_handler,
            'current_view_mode': view_mode
        })
        
        return context


class UserLeaveHistoryView(LoginRequiredMixin, ListView):
    """Ιστορικό αδειών συγκεκριμένου χρήστη"""
    model = LeaveRequest
    template_name = 'leaves/user_leave_history.html'
    context_object_name = 'leave_requests'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        if not (request.user.is_leave_handler or request.user.is_department_manager):
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
        
        # Έλεγχος αν ο προϊστάμενος προσπαθεί να δει χρήστη εκτός της ιεραρχίας του
        if request.user.is_department_manager:
            user_id = self.kwargs['user_id']
            target_user = get_object_or_404(User, pk=user_id)
            
            # Βρίσκω όλα τα τμήματα που ο προϊστάμενος μπορεί να δει
            if request.user.department:
                allowed_departments = request.user.department.get_all_sub_departments()
                if target_user.department not in allowed_departments:
                    raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης στο ιστορικό αυτού του χρήστη.")
            else:
                raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης στο ιστορικό αυτού του χρήστη.")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        user_id = self.kwargs['user_id']
        return LeaveRequest.objects.filter(user_id=user_id).select_related(
            'leave_type', 'manager_approved_by', 'processed_by', 'rejected_by'
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.kwargs['user_id']
        user = get_object_or_404(User, pk=user_id)
        context['selected_user'] = user
        
        # Στατιστικά για αυτόν τον χρήστη
        all_requests = LeaveRequest.objects.filter(user=user)
        context.update({
            'total_requests': all_requests.count(),
            'completed_requests': all_requests.filter(status='COMPLETED').count(),
            'pending_requests': all_requests.filter(status__in=['SUBMITTED', 'PENDING_PROTOCOL', 'IN_REVIEW']).count(),
            'rejected_requests': all_requests.filter(status__in=['SUPERVISOR_REJECTED', 'REJECTED_BY_LEAVES_DEPT']).count(),
            'total_days_used': sum(req.total_days for req in all_requests.filter(status='COMPLETED')),
            'user_role': 'handler' if self.request.user.is_leave_handler else 'manager'
        })
        
        return context


@login_required
def complete_leave_request(request, pk):
    """Ολοκλήρωση αίτησης — GET: confirmation page, POST: execute"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα ολοκλήρωσης.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if request.method == 'GET':
        if leave_request.status not in ['IN_REVIEW']:
            messages.error(request, 'Η αίτηση δεν είναι σε κατάσταση επεξεργασίας.')
            return redirect('leaves:leave_request_detail', pk=pk)
        
        from leaves.utils.balance_ledger import get_last_balance
        current_balance = get_last_balance(leave_request.user)
        if current_balance is None:
            current_balance = leave_request.user.current_regular_leave_balance
        
        suggested_balance = max(0, current_balance - leave_request.total_days) if leave_request.leave_type.affects_regular_leave_balance else current_balance
        
        return render(request, 'leaves/complete_leave_confirm.html', {
            'leave_request': leave_request,
            'current_balance': current_balance,
            'suggested_balance': suggested_balance,
        })
    
    comments = request.POST.get('comments', '')
    protocol_number = request.POST.get('protocol_number', '')
    balance_after = request.POST.get('balance_after', '')
    
    try:
        if protocol_number:
            leave_request.protocol_number = protocol_number
            leave_request.save()
        
        if leave_request.leave_type.affects_regular_leave_balance:
            if not balance_after:
                messages.error(request, 'Απαιτείται η καταχώρηση του υπολοίπου κανονικών αδειών μετά την πράξη.')
                return redirect('leaves:leave_request_detail', pk=pk)
            
            try:
                balance_after = int(balance_after)
            except (ValueError, TypeError):
                messages.error(request, 'Το υπόλοιπο πρέπει να είναι ακέραιος αριθμός.')
                return redirect('leaves:leave_request_detail', pk=pk)
        
        leave_request.complete_by_handler(request.user, comments)
        
        if leave_request.leave_type.affects_regular_leave_balance and balance_after:
            from leaves.utils.balance_ledger import create_balance_entry
            from leaves.utils.balance_ledger import get_last_balance
            last_balance = get_last_balance(leave_request.user)
            days_delta = None
            if last_balance is not None:
                days_delta = balance_after - last_balance
            
            create_balance_entry(
                employee=leave_request.user,
                entry_type='LEAVE_GRANTED',
                description=f'Ολοκλήρωση άδειας #{leave_request.id} — {leave_request.leave_type.name}',
                balance_after=balance_after,
                leave_request=leave_request,
                days_delta=days_delta,
                notes=comments or f'Ημερομηνίες: {leave_request.start_date} - {leave_request.end_date}',
                created_by=request.user
            )
        
        from notifications.utils import create_notification
        create_notification(
            user=leave_request.user,
            title="Αίτηση Ολοκληρώθηκε",
            message=f"Η αίτησή σας για {leave_request.leave_type.name} ολοκληρώθηκε επιτυχώς",
            related_object=leave_request
        )
        
        # Alert για Υγειονομική Επιτροπή
        if leave_request.leave_type.is_sick_leave_total and leave_request.user.sick_days_current_year > 8:
            from accounts.models import User
            handlers = User.objects.filter(roles__code='LEAVE_HANDLER', is_active=True)
            for handler in handlers:
                create_notification(
                    user=handler,
                    title="Υγειονομική Επιτροπή",
                    message=(
                        f"Ο/Η {leave_request.user.full_name} έχει ξεπεράσει τις 8 αναρρωτικές ημέρες "
                        f"({leave_request.user.sick_days_current_year} ημέρες). Απαιτείται παραπομπή."
                    ),
                    related_object=leave_request
                )
            create_notification(
                user=leave_request.user,
                title="Υγειονομική Επιτροπή",
                message=(
                    f"Το σύνολο των αναρρωτικών σας αδειών ({leave_request.user.sick_days_current_year} ημέρες) "
                    f"ξεπερνά το όριο των 8 ημερών. Απαιτείται παραπομπή στην Υγειονομική Επιτροπή."
                ),
                related_object=leave_request
            )
        
        messages.success(request, 'Η αίτηση ολοκληρώθηκε επιτυχώς!')
        
    except Exception as e:
        messages.error(request, f'Σφάλμα κατά την ολοκλήρωση: {str(e)}')
    
    return redirect('leaves:handler_dashboard')


@login_required
def reject_leave_request_by_handler(request, pk):
    """Απόρριψη αίτησης από χειριστή αδειών"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα απόρριψης.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος αν η αίτηση μπορεί να απορριφθεί από handler
    if leave_request.status not in ['PENDING_PROTOCOL', 'IN_REVIEW', 'WAITING_FOR_DOCUMENTS',
                                     'DECISION_PREPARATION', 'PENDING_SIGNATURES']:
        messages.error(request, 'Η αίτηση δεν μπορεί να απορριφθεί σε αυτή τη φάση.')
        return redirect('leaves:leave_request_detail', pk=leave_request.pk)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        
        if not reason:
            messages.error(request, 'Παρακαλώ συμπληρώστε τον λόγο απόρριψης.')
            return render(request, 'leaves/reject_confirm.html', {'leave_request': leave_request})
        
        try:
            leave_request.reject_by_handler(request.user, reason)
            
            # Ειδοποίηση στον υπάλληλο
            create_notification(
                user=leave_request.user,
                title="Αίτηση Απορρίφθηκε",
                message=f"Η αίτησή σας για {leave_request.leave_type.name} απορρίφθηκε από τον χειριστή αδειών",
                related_object=leave_request
            )
            
            # Ειδοποίηση στον προϊστάμενο
            if leave_request.manager_approved_by:
                create_notification(
                    user=leave_request.manager_approved_by,
                    title="Αίτηση Απορρίφθηκε από Χειριστή",
                    message=f"Η αίτηση του/της {leave_request.user.full_name} για {leave_request.leave_type.name} απορρίφθηκε από τον χειριστή αδειών",
                    related_object=leave_request
                )
            
            messages.success(request, 'Η αίτηση απορρίφθηκε επιτυχώς!')
            return redirect('leaves:handler_dashboard')
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την απόρριψη: {str(e)}')
            return render(request, 'leaves/reject_confirm.html', {'leave_request': leave_request})
    
    # GET: Εμφάνιση σελίδας επιβεβαίωσης απόρριψης
    return render(request, 'leaves/reject_confirm.html', {'leave_request': leave_request})


@login_required
def send_to_protocol_pdede(request, pk):
    """Αποθήκευση στοιχείων ΠΔΕΔΕ/ΣΗΔΕ πρωτοκόλλου και προώθηση σε επεξεργασία"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα επεξεργασίας.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if leave_request.status != 'PENDING_PROTOCOL':
        messages.error(request, 'Η αίτηση δεν μπορεί να σταλεί για πρωτόκολλο σε αυτή τη φάση.')
        return redirect('leaves:handler_dashboard')
    
    if request.method == 'POST':
        protocol_number = request.POST.get('protocol_number', '').strip()
        protocol_date_str = request.POST.get('protocol_date', '').strip()
        
        if not protocol_number:
            messages.error(request, 'Παρακαλώ συμπληρώστε τον αριθμό πρωτοκόλλου ΠΔΕΔΕ.')
            return redirect('leaves:handler_dashboard')
        
        try:
            # Μετατροπή ημερομηνίας (πεδίο date type=date επιστρέφει YYYY-MM-DD)
            from datetime import datetime
            protocol_date = None
            if protocol_date_str:
                protocol_date = datetime.strptime(protocol_date_str, '%Y-%m-%d').date()
                # Μετατροπή σε datetime τοπικής ώρας
                protocol_date = datetime.combine(protocol_date, datetime.min.time())
                protocol_date = timezone.make_aware(protocol_date)
            
            # Αποθήκευση στοιχείων ΠΔΕΔΕ
            protocol_details = request.POST.get('protocol_details', '').strip()
            leave_request.save_pdede_protocol_details(
                protocol_number=protocol_number,
                protocol_date=protocol_date,
                protocol_details=protocol_details,
                user=request.user
            )
            
            # Αλλαγή status σε IN_REVIEW για να προχωρήσει στην επεξεργασία
            leave_request.status = 'IN_REVIEW'
            leave_request.save()
            
            # Δημιουργία ιστορικού
            try:
                from .models import LeaveRequestHistory
                LeaveRequestHistory.objects.create(
                    leave_request=leave_request,
                    action='PDEDE_PROTOCOL_SUBMITTED',
                    user=request.user,
                    notes=f'Αποστολή για ΠΔΕΔΕ πρωτόκολλο. Αρ. Πρωτ: {protocol_number}'
                )
            except Exception:
                pass
            
            # Ειδοποίηση στον υπάλληλο
            try:
                create_notification(
                    user=leave_request.user,
                    title="Αίτηση προχώρησε σε επεξεργασία",
                    message=f"Η αίτησή σας για {leave_request.leave_type.name} καταχωρήθηκε με αριθμό πρωτοκόλλου ΠΔΕΔΕ {protocol_number} και προχωρά σε επεξεργασία.",
                    related_object=leave_request
                )
            except Exception as notification_error:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Notification error in send_to_protocol_pdede: {notification_error}")
            
            messages.success(request, f'Η αίτηση καταχωρήθηκε με αριθμό πρωτοκόλλου ΠΔΕΔΕ {protocol_number} και προχωρά σε επεξεργασία!')
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την αποστολή: {str(e)}')
    
    return redirect('leaves:handler_dashboard')


@login_required
def upload_protocol_pdf(request, pk):
    """Ανέβασμα του πρωτοκολλημένου PDF από το ΣΗΔΕ"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα επεξεργασίας.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if leave_request.status != 'PENDING_PROTOCOL':
        messages.error(request, 'Δεν μπορείτε να ανεβάσετε πρωτοκολλημένο PDF σε αυτή τη φάση.')
        return redirect('leaves:handler_dashboard')
    
    if request.method == 'POST':
        protocol_number = request.POST.get('protocol_number', '').strip()
        protocol_pdf = request.FILES.get('protocol_pdf')
        
        if not protocol_number:
            messages.error(request, 'Παρακαλώ συμπληρώστε τον αριθμό πρωτοκόλλου.')
            return redirect('leaves:handler_dashboard')
        
        if not protocol_pdf:
            messages.error(request, 'Παρακαλώ ανεβάστε το πρωτοκολλημένο PDF.')
            return redirect('leaves:handler_dashboard')
        
        try:
            # Αποθήκευση του πρωτοκολλημένου PDF στο LeaveRequest
            from .crypto_utils import SecureFileHandler
            from django.conf import settings
            import os
            
            private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                                       os.path.join(settings.BASE_DIR, 'private_media'))
            
            file_path = os.path.join(
                private_media_root,
                'leave_requests',
                str(leave_request.id),
                f"protocol_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{protocol_pdf.name}"
            )
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            success, key_hex, file_size = SecureFileHandler.save_encrypted_file(protocol_pdf, file_path)
            
            if success:
                # Ενημέρωση της αίτησης με τα στοιχεία του πρωτοκολλημένου PDF
                leave_request.protocol_number = protocol_number
                leave_request.protocol_pdf_path = file_path
                leave_request.protocol_pdf_encryption_key = key_hex
                leave_request.protocol_pdf_size = file_size
                leave_request.protocol_created_at = timezone.now()
                leave_request.status = 'IN_REVIEW'
                leave_request.save()
                
                # Ειδοποίηση στον υπάλληλο (προσωρινά απενεργοποιημένη)
                try:
                    create_notification(
                        user=leave_request.user,
                        title="Αίτηση Πρωτοκολλήθηκε",
                        message=f"Η αίτησή σας για {leave_request.leave_type.name} πρωτοκολλήθηκε με αριθμό {protocol_number} και βρίσκεται υπό επεξεργασία",
                        related_object=leave_request
                    )
                except Exception as notification_error:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Notification error in upload_protocol_pdf: {notification_error}")
                
                messages.success(request, f'Το πρωτοκολλημένο PDF ανέβηκε επιτυχώς! Αρ. Πρωτ: {protocol_number}')
            else:
                messages.error(request, 'Σφάλμα κατά την αποθήκευση του αρχείου.')
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά το ανέβασμα: {str(e)}')
    
    return redirect('leaves:handler_dashboard')


@login_required
def serve_protocol_pdf(request, pk):
    """Serve του πρωτοκολλημένου PDF"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    user = request.user
    
    # Έλεγχος δικαιωμάτων
    can_view = (
        leave_request.user == user or  # Ο ίδιος ο αιτών
        (user.is_department_manager and user.department and leave_request.user.department and user.department.id == leave_request.user.department.id) or  # Στο ίδιο τμήμα
        user.is_leave_handler or  # Χειριστής αδειών
        user.is_administrator  # Διαχειριστής
    )
    
    # Έλεγχος αν είναι προϊστάμενος ΚΕΔΑΣΥ και η αίτηση από ΣΔΕΥ
    if (not can_view and user.is_department_manager and
        user.department and user.department.department_type and
        user.department.department_type.code == 'KEDASY' and
        leave_request.user.department and leave_request.user.department.department_type and
        leave_request.user.department.department_type.code == 'SDEY' and
        leave_request.user.department.parent_department == user.department):
        can_view = True
    
    if not can_view:
        raise PermissionDenied("Δεν έχετε δικαίωμα προβολής αυτού του αρχείου.")
    
    if not leave_request.has_protocol_pdf:
        raise Http404("Το πρωτοκολλημένο PDF δεν βρέθηκε.")
    
    try:
        from .crypto_utils import SecureFileHandler
        
        # Αποκρυπτογράφηση και serve του αρχείου
        decrypted_content = SecureFileHandler.load_encrypted_file(
            leave_request.protocol_pdf_path,
            leave_request.protocol_pdf_encryption_key
        )
        
        if decrypted_content is None:
            raise Http404("Σφάλμα κατά την αποκρυπτογράφηση του αρχείου.")
        
        response = HttpResponse(decrypted_content, content_type='application/pdf')
        filename = f"Πρωτοκολλημένη_Αίτηση_{leave_request.protocol_number or leave_request.id}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Content-Length'] = len(decrypted_content)
        
        return response
        
    except Exception as e:
        raise Http404(f"Σφάλμα κατά τη φόρτωση του αρχείου: {str(e)}")


class LeaveRequestDetailView(LoginRequiredMixin, DetailView):
    """Λεπτομέρειες αίτησης άδειας"""
    model = LeaveRequest
    template_name = 'leaves/leave_request_detail.html'
    context_object_name = 'leave_request'
    
    def get_object(self):
        obj = super().get_object()
        user = self.request.user
        
        # Έλεγχος δικαιωμάτων
        can_view = (
            obj.user == user or  # Ο ίδιος ο αιτών
            (user.is_department_manager and user.department and obj.user.department and user.department.id == obj.user.department.id) or  # Στο ίδιο τμήμα
            (user.is_secretary and user.department and obj.user.department and user.department.id == obj.user.department.id) or  # Γραμματέας στο ίδιο τμήμα
            user.is_leave_handler or  # Χειριστής αδειών
            user.is_administrator  # Διαχειριστής
        )
        
        # Έλεγχος αν είναι προϊστάμενος ΚΕΔΑΣΥ και η αίτηση από ΣΔΕΥ
        if (not can_view and user.is_department_manager and
            user.department and user.department.department_type and
            user.department.department_type.code == 'KEDASY' and
            obj.user.department and obj.user.department.department_type and
            obj.user.department.department_type.code == 'SDEY' and
            obj.user.department.parent_department == user.department):
            can_view = True
        
        # Έλεγχος αν είναι γραμματέας ΚΕΔΑΣΥ και η αίτηση από ΣΔΕΥ
        if (not can_view and user.is_secretary and
            user.department and user.department.department_type and
            user.department.department_type.code == 'KEDASY' and
            obj.user.department and obj.user.department.department_type and
            obj.user.department.department_type.code == 'SDEY' and
            obj.user.department.parent_department == user.department):
            can_view = True
            
        # Έλεγχος αν είναι προϊστάμενος της Αυτοτελούς Διεύθυνσης και η αίτηση από child departments
        if (not can_view and user.is_department_manager and
            user.department and user.department.code == 'AUTOTELOUS_DN' and
            obj.user.department and obj.user.department.parent_department == user.department):
            can_view = True
        
        # Έλεγχος αν είναι προϊστάμενος PDEDE και η αίτηση από AUTOTELOUS_DN manager
        if (not can_view and user.is_department_manager and
            user.department and user.department.code == 'PDEDE' and
            obj.user.department and obj.user.department.code == 'AUTOTELOUS_DN' and
            obj.user.is_department_manager):
            can_view = True
        
        if not can_view:
            raise PermissionDenied("Δεν έχετε δικαίωμα προβολής αυτής της αίτησης.")
        
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        leave_request = self.object
        user = self.request.user

        # Attachments
        context['attachments'] = leave_request.attachments.all()

        # Audit trail
        context['action_logs'] = leave_request.action_logs.all().order_by('-timestamp')

        # Locking status
        context['is_locked'] = leave_request.locking_user is not None
        context['locked_by'] = leave_request.locking_user
        context['locked_at'] = leave_request.locked_at
        context['lock_expired'] = False
        if leave_request.locked_at:
            from datetime import timedelta
            cutoff = timezone.now() - timedelta(minutes=LOCK_TIMEOUT_MINUTES)
            context['lock_expired'] = leave_request.locked_at < cutoff

        # Revocation eligibility
        context['can_withdraw'] = False
        context['can_withdraw_completed'] = False
        if user == leave_request.user:
            # Ανάκληση αίτησης (μέχρι ΠΡΟΣ ΕΠΕΞΕΡΓΑΣΙΑ)
            if leave_request.status in ['SUBMITTED', 'PENDING_PROTOCOL']:
                context['can_withdraw'] = True
            # Ανάκληση ολοκληρωμένης
            if leave_request.status == 'COMPLETED':
                context['can_withdraw_completed'] = True

        # Delete by handler (μόνο σε UNDER_PROCESSING)
        context['can_delete'] = user.is_leave_handler and leave_request.status == 'IN_REVIEW'

        # Sick leave attachment restriction
        context['is_sick_leave'] = leave_request.leave_type.name.lower().find('αναρρωτικ') >= 0
        context['can_view_attachments'] = True
        if context['is_sick_leave'] and user.is_department_manager and user != leave_request.user:
            context['can_view_attachments'] = False
        if user.is_department_manager and leave_request.user.department and \
           leave_request.user.department.department_type and \
           leave_request.user.department.department_type.code == 'SDEY' and \
           user.department and user.department.department_type and \
           user.department.department_type.code == 'KEDASY' and \
           leave_request.user.department.parent_department == user.department and \
           context['is_sick_leave']:
            context['can_view_attachments'] = False

        return context


# Redirect views για εύκολη πλοήγηση
@login_required
def dashboard_redirect(request):
    """Ανακατεύθυνση στο κατάλληλο dashboard ανάλογα με τον ρόλο"""
    user = request.user
    
    if user.is_leave_handler:
        return redirect('leaves:handler_dashboard')
    elif user.is_department_manager:
        return redirect('leaves:manager_dashboard')
    elif user.is_secretary:
        return redirect('leaves:secretary_dashboard')
    else:
        return redirect('leaves:employee_dashboard')


@login_required
def serve_secure_file(request, file_id):
    """
    Ασφαλής παροχή κρυπτογραφημένων αρχείων με έλεγχο δικαιωμάτων
    Security by Design - Κανένα άμεσο URL σε αρχεία
    """
    try:
        # Εύρεση του αρχείου
        secure_file = get_object_or_404(SecureFile, id=file_id)
        
        # Έλεγχος δικαιωμάτων πρόσβασης
        if not FileAccessController.can_user_access_file(request.user, secure_file):
            # Log της μη εξουσιοδοτημένης προσπάθειας
            FileAccessController.log_file_access(
                user=request.user,
                secure_file=secure_file,
                access_type='VIEW',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτό το αρχείο.")
        
        # Φόρτωση και αποκρυπτογράφηση του αρχείου
        decrypted_content = SecureFileHandler.load_encrypted_file(
            secure_file.file_path,
            secure_file.encryption_key
        )
        
        if decrypted_content is None:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to decrypt file {file_id} for user {request.user.id}")
            raise Http404("Το αρχείο δεν μπορεί να φορτωθεί.")
        
        # Καταγραφή επιτυχούς πρόσβασης (GDPR)
        access_type = 'DOWNLOAD' if request.GET.get('download') else 'VIEW'
        FileAccessController.log_file_access(
            user=request.user,
            secure_file=secure_file,
            access_type=access_type,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        # Προσδιορισμός Content-Type
        content_type = secure_file.content_type or SecureFileHandler.get_content_type(
            secure_file.original_filename
        )
        
        # Δημιουργία HTTP Response
        response = HttpResponse(decrypted_content, content_type=content_type)
        
        # Headers για ασφαλή διαχείριση
        response['Content-Disposition'] = f'inline; filename="{secure_file.original_filename}"'
        response['Content-Length'] = len(decrypted_content)
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        # Καθαρισμός μνήμης
        del decrypted_content
        
        return response
        
    except SecureFile.DoesNotExist:
        raise Http404("Το αρχείο δεν βρέθηκε.")
    
    except PermissionDenied:
        raise
    
    except Exception as e:
        # Log του σφάλματος
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error serving secure file {file_id}: {str(e)}")
        
        return HttpResponse(
            "Σφάλμα κατά τη φόρτωση του αρχείου.",
            status=500,
            content_type="text/plain"
        )


@login_required
def delete_secure_file(request, file_id):
    """
    Διαγραφή κρυπτογραφημένου αρχείου (μόνο από τον ιδιοκτήτη της αίτησης)
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Μόνο POST requests επιτρέπονται'}, status=405)
    
    try:
        secure_file = get_object_or_404(SecureFile, id=file_id)
        
        # Έλεγχος δικαιωμάτων - μόνο ο ιδιοκτήτης της αίτησης μπορεί να διαγράψει
        if secure_file.leave_request.user != request.user:
            return JsonResponse({'error': 'Δεν έχετε δικαίωμα διαγραφής'}, status=403)
        
        # Έλεγχος αν η αίτηση μπορεί να επεξεργαστεί
        if not secure_file.leave_request.can_be_edited:
            return JsonResponse({'error': 'Δεν μπορείτε να διαγράψετε αρχεία από υποβλημένη αίτηση'}, status=400)
        
        # Διαγραφή του φυσικού αρχείου
        success = SecureFileHandler.delete_encrypted_file(secure_file.file_path)
        
        # Διαγραφή της εγγραφής από τη βάση
        filename = secure_file.original_filename
        secure_file.delete()
        
        if success:
            return JsonResponse({
                'success': True,
                'message': f'Το αρχείο "{filename}" διαγράφηκε επιτυχώς.'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Το αρχείο διαγράφηκε από τη βάση αλλά υπήρξε πρόβλημα με το φυσικό αρχείο.'
            })
            
    except SecureFile.DoesNotExist:
        return JsonResponse({'error': 'Το αρχείο δεν βρέθηκε'}, status=404)
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error deleting secure file {file_id}: {str(e)}")
        
        return JsonResponse({'error': 'Σφάλμα κατά τη διαγραφή'}, status=500)

@login_required
def submit_final_request(request):
    """Handle final submission of leave request and create PDF"""
    if request.method == 'POST':
        from django.utils import timezone
        from .models import LeaveRequest, LeavePeriod, LeaveType, SecureFile
        from .crypto_utils import SecureFileHandler
        from django.conf import settings
        import os
        from weasyprint import HTML
        from django.template.loader import render_to_string
        from notifications.utils import create_notification
        from django.contrib import messages
        from django.shortcuts import redirect
        from django.http import HttpResponse
        
        # Παίρνουμε το ID της αίτησης που δημιουργήθηκε ως DRAFT
        leave_request_id = request.POST.get('leave_request_id')
        
        if not leave_request_id:
            messages.error(request, 'Σφάλμα: Δεν βρέθηκε η αίτηση.')
            return redirect('leaves:create_leave_request')
        
        try:
            # Βρίσκουμε την αίτηση που δημιουργήθηκε ως DRAFT
            leave_request = LeaveRequest.objects.get(id=leave_request_id, user=request.user, status='DRAFT')
            
            # Ενημερώνουμε την περιγραφή αν άλλαξε
            new_description = request.POST.get('description')
            if new_description:
                leave_request.description = new_description
            
            # Χρησιμοποιούμε τη μέθοδο submit() από το model που έχει τον έλεγχο για το leave balance
            try:
                leave_request.submit()
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('leaves:create_leave_request')
            
            # Ειδοποιήσεις ανάλογα με τον τύπο άδειας και τμήμα
            if leave_request.leave_type.requires_approval:
                if leave_request.is_kedasy_kepea_department():
                    # Για ΚΕΔΑΣΥ/ΚΕΠΕΑ/ΣΔΕΥ: ειδοποίηση γραμματέα/προϊσταμένου για πρωτόκολλο
                    target_department = leave_request.user.department
                    if (leave_request.user.department.department_type and
                        leave_request.user.department.department_type.code == 'SDEY' and
                        leave_request.user.department.parent_department):
                        target_department = leave_request.user.department.parent_department
                    
                    # Ειδοποίηση γραμματέα
                    secretaries = User.objects.filter(
                        roles__code='SECRETARY',
                        is_active=True,
                        department=target_department
                    ).distinct()
                    for secretary in secretaries:
                        create_notification(
                            user=secretary,
                            title="Νέα Αίτηση προς Πρωτοκόλληση ΚΕΔΑΣΥ/ΚΕΠΕΑ",
                            message=f"Νέα αίτηση άδειας από {leave_request.user.full_name} για {leave_request.leave_type.name} - χρειάζεται πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ πριν την έγκριση",
                            related_object=leave_request
                        )
                    
                    # Ειδοποίηση προϊσταμένου
                    manager_to_notify = leave_request.user.get_approving_manager()
                    if manager_to_notify:
                        create_notification(
                            user=manager_to_notify,
                            title="Νέα Αίτηση προς Πρωτοκόλληση ΚΕΔΑΣΥ/ΚΕΠΕΑ",
                            message=f"Νέα αίτηση άδειας από {leave_request.user.full_name} για {leave_request.leave_type.name} - αναμένει πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ",
                            related_object=leave_request
                        )
                else:
                    # Κανονική ροή - ειδοποίηση προϊσταμένου
                    approving_manager = leave_request.user.get_approving_manager()
                    if approving_manager:
                        create_notification(
                            user=approving_manager,
                            title="Νέα Αίτηση Άδειας",
                            message=f"Νέα αίτηση άδειας από {leave_request.user.full_name} για {leave_request.leave_type.name}",
                            related_object=leave_request
                        )
            else:
                # Έλεγχος αν ο χρήστης ανήκει σε τμήμα ΚΕΔΑΣΥ/ΚΕΠΕΑ ή ΣΔΕΥ με parent ΚΕΔΑΣΥ
                if leave_request.is_kedasy_kepea_department():
                    # Για ΚΕΔΑΣΥ/ΚΕΠΕΑ/ΣΔΕΥ, ειδοποίηση γραμματέα και προϊσταμένου για πρωτόκολλο
                    # Για ΣΔΕΥ, βρίσκουμε τους γραμματείς του parent ΚΕΔΑΣΥ
                    target_department = leave_request.user.department
                    if (leave_request.user.department.department_type and
                        leave_request.user.department.department_type.code == 'SDEY' and
                        leave_request.user.department.parent_department):
                        target_department = leave_request.user.department.parent_department
                    
                    # Ειδοποίηση γραμματέα
                    secretaries = User.objects.filter(
                        roles__code='SECRETARY',
                        is_active=True,
                        department=target_department
                    ).distinct()
                    for secretary in secretaries:
                        create_notification(
                            user=secretary,
                            title="Νέα Αίτηση ΚΕΔΑΣΥ/ΚΕΠΕΑ για Πρωτόκολλο",
                            message=f"Νέα αίτηση άδειας από {leave_request.user.full_name} για {leave_request.leave_type.name} - χρειάζεται πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ",
                            related_object=leave_request
                        )
                    
                    # Ειδοποίηση προϊσταμένου - για ΣΔΕΥ, ειδοποιούμε τον ΚΕΔΑΣΥ προϊστάμενο
                    manager_to_notify = leave_request.user.manager
                    if (leave_request.user.department.department_type and
                        leave_request.user.department.department_type.code == 'SDEY' and
                        leave_request.user.department.parent_department):
                        # Βρίσκουμε τον προϊστάμενο του ΚΕΔΑΣΥ
                        kedasy_managers = User.objects.filter(
                            roles__code='MANAGER',
                            department=leave_request.user.department.parent_department,
                            is_active=True
                        ).distinct()
                        if kedasy_managers.exists():
                            manager_to_notify = kedasy_managers.first()
                    
                    if manager_to_notify:
                        create_notification(
                            user=manager_to_notify,
                            title="Νέα Αίτηση ΚΕΔΑΣΥ/ΚΕΠΕΑ για Πρωτόκολλο",
                            message=f"Νέα αίτηση άδειας από {leave_request.user.full_name} για {leave_request.leave_type.name} - χρειάζεται πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ",
                            related_object=leave_request
                        )
                else:
                    # Παράκαμψη προϊσταμένου - ειδοποίηση χειριστών αδειών
                    leave_handlers = User.objects.filter(roles__code='LEAVE_HANDLER', is_active=True).distinct()
                    for handler in leave_handlers:
                        create_notification(
                            user=handler,
                            title="Νέα Αίτηση Άδειας (Άμεση Επεξεργασία)",
                            message=f"Νέα αίτηση άδειας από {leave_request.user.full_name} για {leave_request.leave_type.name} - δεν απαιτεί έγκριση προϊσταμένου",
                            related_object=leave_request
                        )
            
            # Προσθήκη νέων συνημμένων αρχείων αν υπάρχουν
            private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                                       os.path.join(settings.BASE_DIR, 'private_media'))
            
            for key in request.FILES.keys():
                if key.startswith('attachment_'):
                    file_obj = request.FILES[key]
                    index = key.replace('attachment_', '')
                    description_key = f'attachment_description_{index}'
                    description = request.POST.get(description_key, '')
                    if file_obj:
                        # Επικύρωση αρχείου πριν την αποθήκευση
                        is_valid, error_message = SecureFileHandler.validate_file(file_obj)
                        if not is_valid:
                            return JsonResponse({'success': False, 'error': f'Αρχείο "{file_obj.name}": {error_message}'}, status=400)
                        
                        try:
                            file_path = os.path.join(
                                private_media_root,
                                'leave_requests',
                                str(leave_request.id),
                                f"{timezone.now().strftime('%Y%m%d_%H%M%S')}_{file_obj.name}"
                            )
                            os.makedirs(os.path.dirname(file_path), exist_ok=True)
                            success, key_hex, file_size = SecureFileHandler.save_encrypted_file(file_obj, file_path)
                            
                            if success:
                                SecureFile.objects.create(
                                    leave_request=leave_request,
                                    original_filename=file_obj.name,
                                    file_path=file_path,
                                    file_size=file_size,
                                    content_type=file_obj.content_type,
                                    encryption_key=key_hex,
                                    uploaded_by=request.user,
                                    description=description if description else f"Συνημμένο {index}"
                                )
                        except Exception as e:
                            import logging
                            logger = logging.getLogger(__name__)
                            logger.error(f"Error handling file upload {file_obj.name}: {str(e)}")
            
            # Generate PDF
            pdf_path = os.path.join(private_media_root, 'leave_requests', str(leave_request.id), 'request.pdf')
            os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
            
            # Ensure we're using the same context as preview
            # Refresh leave_request from database to ensure relationships are loaded
            leave_request.refresh_from_db()
            
            # Get attachments after they have been created
            attachments = leave_request.attachments.all()
            
            context = {
                'leave_request': leave_request,
                'user': request.user,
                'periods': leave_request.periods.all(),
                'request_text': request.POST.get('request_text', ''),
                'attachments': attachments,
                'form_data': {
                    'description': leave_request.description,
                    'leave_type': leave_request.leave_type
                }
            }
            
            # Generate PDF
            html_content = render_to_string('leaves/pdf_template.html', context)
            HTML(string=html_content).write_pdf(pdf_path)
            
            messages.success(request, 'Η αίτηση άδειας υποβλήθηκε επιτυχώς!')
            return redirect('leaves:leave_request_detail', leave_request.id)
            
        except LeaveRequest.DoesNotExist:
            messages.error(request, 'Σφάλμα: Η αίτηση δεν βρέθηκε ή δεν ανήκει σε εσάς.')
            return redirect('leaves:create_leave_request')
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in submit_final_request: {str(e)}")
            messages.error(request, f'Σφάλμα κατά την υποβολή της αίτησης: {str(e)}')
            return redirect('leaves:create_leave_request')
    
    return redirect('leaves:create_leave_request')
        


@login_required
def download_leave_pdf(request, request_id):
    """Download PDF for a leave request"""
    from django.conf import settings
    import os
    
    # Get the leave request
    try:
        leave_request = LeaveRequest.objects.get(id=request_id)
    except LeaveRequest.DoesNotExist:
        raise Http404("Η αίτηση δεν βρέθηκε")
    
    # Check permissions
    if not (request.user == leave_request.user or
            request.user.is_department_manager or
            request.user.is_leave_handler or
            request.user.is_secretary):
        raise Http404("Δεν έχετε δικαίωμα πρόσβασης")
    
    # Check if PDF exists
    private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                               os.path.join(settings.BASE_DIR, 'private_media'))
    pdf_path = os.path.join(private_media_root, 'leave_requests', str(leave_request.id), 'request.pdf')
    
    if not os.path.exists(pdf_path):
        raise Http404("Το PDF δεν βρέθηκε")
    
    # Return PDF
    try:
        with open(pdf_path, 'rb') as pdf:
            response = HttpResponse(pdf.read(), content_type='application/pdf')
            user = leave_request.user
            date_str = leave_request.created_at.strftime('%d/%m/%Y')
            
            filename = f'{user.last_name} {user.first_name} - Αίτηση άδειας - {date_str}.pdf'
            
            from django.utils.encoding import iri_to_uri
            filename_encoded = iri_to_uri(filename)

            # If download parameter is set, force download, otherwise inline view
            if request.GET.get('download'):
                response['Content-Disposition'] = f'attachment; filename="{filename_encoded}"'
            else:
                response['Content-Disposition'] = f'inline; filename="{filename_encoded}"'
            return response
    except Exception:
        raise Http404("Σφάλμα κατά τη λήψη του PDF")

class SecretaryDashboardView(LoginRequiredMixin, ListView):
    """Dashboard για Γραμματεία ΚΕΔΑΣΥ/ΚΕΠΕΑ - Αιτήσεις προς πρωτοκόλληση"""
    model = LeaveRequest
    template_name = 'leaves/secretary_dashboard.html'
    context_object_name = 'leave_requests'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_secretary:
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Αιτήσεις ΚΕΔΑΣΥ/ΚΕΠΕΑ που περιμένουν πρωτόκολλο
        if self.request.user.department:
            department_filter = Q(
                status='PENDING_KEDASY_PROTOCOL',
                user__department=self.request.user.department
            )
            
            if (self.request.user.department.department_type and
                self.request.user.department.department_type.code == 'KEDASY'):
                sdei_condition = Q(
                    status='PENDING_KEDASY_PROTOCOL',
                    user__department__department_type__code='SDEY',
                    user__department__parent_department=self.request.user.department
                )
                department_filter = department_filter | sdei_condition
            
            return LeaveRequest.objects.filter(department_filter).select_related(
                'user', 'user__department', 'user__department__department_type', 'leave_type'
            ).order_by('-submitted_at')
        return LeaveRequest.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Στατιστικά για το τμήμα του γραμματέα και ΣΔΕΥ τμήματα αν είναι ΚΕΔΑΣΥ
        if self.request.user.department:
            # Βασικό φίλτρο για το τμήμα του γραμματέα
            department_filter = Q(user__department=self.request.user.department)
            
            # Αν ο γραμματέας είναι σε ΚΕΔΑΣΥ, προσθέτουμε και ΣΔΕΥ τμήματα
            if (self.request.user.department.department_type and
                self.request.user.department.department_type.code == 'KEDASY'):
                
                sdei_filter = Q(
                    user__department__department_type__code='SDEY',
                    user__department__parent_department=self.request.user.department
                )
                department_filter = department_filter | sdei_filter
            
            context.update({
                'pending_protocol_count': self.get_queryset().count(),
                'completed_this_month': LeaveRequest.objects.filter(
                    kedasy_kepea_protocol_date__month=timezone.now().month,
                    kedasy_kepea_protocol_number__isnull=False
                ).filter(department_filter).count(),
                'total_processed': LeaveRequest.objects.filter(
                    kedasy_kepea_protocol_number__isnull=False
                ).filter(department_filter).count(),
            })
            
            # Πρόσφατα πρωτοκολλημένες από το τμήμα του γραμματέα και ΣΔΕΥ
            recent_qs = LeaveRequest.objects.filter(
                kedasy_kepea_protocol_number__isnull=False
            ).filter(department_filter).select_related(
                'user', 'user__department', 'leave_type', 'kedasy_kepea_protocol_by'
            ).order_by('-kedasy_kepea_protocol_date')
            
            # Φίλτρο αναζήτησης
            q = self.request.GET.get('q', '').strip()
            if q:
                from django.db.models import Q
                recent_qs = recent_qs.filter(
                    Q(user__first_name__icontains=q) |
                    Q(user__last_name__icontains=q) |
                    Q(user__department__name__icontains=q) |
                    Q(leave_type__name__icontains=q) |
                    Q(kedasy_kepea_protocol_number__icontains=q) |
                    Q(kedasy_kepea_protocol_by__first_name__icontains=q) |
                    Q(kedasy_kepea_protocol_by__last_name__icontains=q)
                )
            
            context['recent_processed'] = recent_qs[:20]
            context['search_query'] = q
        else:
            context.update({
                'pending_protocol_count': 0,
                'completed_this_month': 0,
                'total_processed': 0,
            })
            context['recent_processed'] = []
        
        context['today'] = timezone.now().date()
        
        return context


@login_required
def withdraw_leave_request(request, pk):
    """Ανάκληση αίτησης από τον αιτούντα"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος αν ο χρήστης είναι ο αιτούντας
    if leave_request.user != request.user:
        raise PermissionDenied("Μόνο ο αιτούντας μπορεί να ανακαλέσει την αίτηση.")
    
    # Έλεγχος αν η αίτηση μπορεί να ανακληθεί
    if not leave_request.can_be_withdrawn:
        messages.error(request, 'Η αίτηση δεν μπορεί να ανακληθεί σε αυτή τη φάση.')
        return redirect('leaves:leave_request_detail', pk=leave_request.pk)
    
    if request.method == 'POST':
        try:
            # Ανάκληση αίτησης
            leave_request.withdraw_by_requester(request.user)
            
            # Ειδοποίηση στον προϊστάμενο αν η αίτηση είχε εγκριθεί
            if leave_request.manager_approved_by:
                create_notification(
                    user=leave_request.manager_approved_by,
                    title="Ανάκληση Αίτησης",
                    message=f"Η αίτηση του/της {leave_request.user.full_name} για {leave_request.leave_type.name} ανακλήθηκε από τον αιτούντα",
                    related_object=leave_request
                )
            
            # Ειδοποίηση στους χειριστές αδειών
            leave_handlers = User.objects.filter(roles__code='LEAVE_HANDLER', is_active=True).distinct()
            for handler in leave_handlers:
                create_notification(
                    user=handler,
                    title="Ανάκληση Αίτησης",
                    message=f"Η αίτηση του/της {leave_request.user.full_name} για {leave_request.leave_type.name} ανακλήθηκε από τον αιτούντα",
                    related_object=leave_request
                )
            
            messages.success(request, 'Η αίτηση ανακλήθηκε επιτυχώς!')
            return redirect('leaves:employee_dashboard')
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την ανάκληση: {str(e)}')
            return redirect('leaves:leave_request_detail', pk=leave_request.pk)
    
    # GET: Εμφάνιση σελίδας επιβεβαίωσης
    return render(request, 'leaves/withdraw_confirm.html', {'leave_request': leave_request})


@login_required
def add_kedasy_kepea_protocol(request, pk):
    """Προσθήκη πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ από γραμματεία ή προϊστάμενο"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος δικαιωμάτων - πρέπει να είναι secretary ή manager από ΚΕΔΑΣΥ/ΚΕΠΕΑ
    if not leave_request.can_add_kedasy_kepea_protocol(request.user):
        raise PermissionDenied("Δεν έχετε δικαίωμα προσθήκης πρωτοκόλλου ΚΕΔΑΣΥ/ΚΕΠΕΑ.")
    
    # Έλεγχος αν η αίτηση είναι στο σωστό στάδιο
    if leave_request.status != 'PENDING_KEDASY_PROTOCOL':
        messages.error(request, 'Η αίτηση δεν μπορεί να πρωτοκολληθεί σε αυτή τη φάση.')
        if request.user.is_secretary:
            return redirect('leaves:secretary_dashboard')
        else:
            return redirect('leaves:manager_dashboard')
    
    # Έλεγχος αν η αίτηση ανήκει σε ΚΕΔΑΣΥ/ΚΕΠΕΑ τμήμα
    if not leave_request.is_kedasy_kepea_department():
        messages.error(request, 'Η αίτηση δεν ανήκει σε τμήμα ΚΕΔΑΣΥ ή ΚΕΠΕΑ.')
        if request.user.is_secretary:
            return redirect('leaves:secretary_dashboard')
        else:
            return redirect('leaves:manager_dashboard')
    
    if request.method == 'POST':
        protocol_number = request.POST.get('protocol_number', '').strip()
        protocol_date = request.POST.get('protocol_date', '')
        comments = request.POST.get('comments', '')
        
        if not protocol_number:
            messages.error(request, 'Παρακαλώ συμπληρώστε τον αριθμό πρωτοκόλλου.')
            return redirect('leaves:secretary_dashboard')
        
        try:
            protocol_date_obj = timezone.now().date()
            if protocol_date:
                from datetime import datetime
                protocol_date_obj = datetime.strptime(protocol_date, '%Y-%m-%d').date()
            
            leave_request.add_kedasy_kepea_protocol(
                protocol_number=protocol_number,
                protocol_date=protocol_date_obj,
                user=request.user
            )
            
            # Μετά το πρωτόκολλο, η αίτηση πάει για έγκριση προϊσταμένου
            approving_manager = leave_request.user.get_approving_manager()
            if approving_manager:
                create_notification(
                    user=approving_manager,
                    title="Αίτηση Πρωτοκολλήθηκε - Εκκρεμεί Έγκριση",
                    message=f"Η αίτηση του/της {leave_request.user.full_name} πρωτοκολλήθηκε από ΚΕΔΑΣΥ/ΚΕΠΕΑ με αρ. {protocol_number} και εκκρεμεί η έγκρισή σας",
                    related_object=leave_request
                )
            messages.success(request, f'Το πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ προστέθηκε επιτυχώς! Αρ. Πρωτ: {protocol_number}. Η αίτηση προωθήθηκε για έγκριση.')
            
            # Ειδοποίηση στον υπάλληλο
            create_notification(
                user=leave_request.user,
                title="Αίτηση Πρωτοκολλήθηκε από ΚΕΔΑΣΥ/ΚΕΠΕΑ",
                message=f"Η αίτησή σας για {leave_request.leave_type.name} πρωτοκολλήθηκε με αρ. {protocol_number} και προχωρά στο επόμενο στάδιο",
                related_object=leave_request
            )
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την προσθήκη του πρωτοκόλλου: {str(e)}')
    
    if request.user.is_secretary:
        return redirect('leaves:secretary_dashboard')
    else:
        return redirect('leaves:manager_dashboard')


@login_required
def request_documents(request, pk):
    """Αίτημα δικαιολογητικών από χειριστή αδειών"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα αιτήματος δικαιολογητικών.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if not leave_request.can_request_documents:
        messages.error(request, 'Δεν μπορεί να ζητηθούν δικαιολογητικά σε αυτή τη φάση.')
        return redirect('leaves:leave_request_detail', pk=leave_request.pk)
    
    if request.method == 'POST':
        required_documents = request.POST.get('required_documents', '').strip()
        deadline_date = request.POST.get('deadline_date', '')
        deadline_time = request.POST.get('deadline_time', '')
        
        if not required_documents:
            messages.error(request, 'Παρακαλώ συμπληρώστε τα απαιτούμενα δικαιολογητικά.')
            return render(request, 'leaves/request_documents_form.html', {
                'leave_request': leave_request,
                'today': timezone.now().date(),
            })
        
        try:
            deadline = None
            if deadline_date:
                from datetime import datetime
                deadline_str = deadline_date
                if deadline_time:
                    deadline_str += f' {deadline_time}'
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%d %H:%M')
                else:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
                    deadline = deadline.replace(hour=23, minute=59)
                deadline = timezone.make_aware(deadline)
            
            leave_request.request_documents(
                handler=request.user,
                required_documents=required_documents,
                deadline=deadline,
            )
            
            create_notification(
                user=leave_request.user,
                title="Απαιτούνται Δικαιολογητικά",
                message=(
                    f"Για την αίτησή σας για {leave_request.leave_type.name} "
                    f"απαιτούνται επιπλέον δικαιολογητικά: {required_documents}"
                ),
                related_object=leave_request,
            )
            
            if leave_request.manager_approved_by:
                create_notification(
                    user=leave_request.manager_approved_by,
                    title="Απαιτούνται Δικαιολογητικά",
                    message=(
                        f"Η αίτηση του/της {leave_request.user.full_name} "
                        f"για {leave_request.leave_type.name} χρειάζεται επιπλέον δικαιολογητικά"
                    ),
                    related_object=leave_request,
                )
            
            messages.success(request, 'Η αίτηση τέθηκε σε αναμονή δικαιολογητικών.')
            return redirect('leaves:leave_request_detail', pk=leave_request.pk)
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά το αίτημα δικαιολογητικών: {str(e)}')
    
    return render(request, 'leaves/request_documents_form.html', {
        'leave_request': leave_request,
        'today': timezone.now().date(),
    })


@login_required
def provide_documents(request, pk):
    """Παροχή δικαιολογητικών από χειριστή αδειών"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα παροχής δικαιολογητικών.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος αν η αίτηση είναι στο σωστό στάδιο
    if leave_request.status != 'WAITING_FOR_DOCUMENTS':
        messages.error(request, 'Η αίτηση δεν είναι σε αναμονή δικαιολογητικών.')
        return redirect('leaves:leave_request_detail', pk=leave_request.pk)
    
    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()

        saved_count, upload_errors = save_leave_request_attachments_from_request(
            request, leave_request, request.user
        )
        if upload_errors:
            for err in upload_errors:
                messages.error(request, err)
            return render(request, 'leaves/provide_documents_confirm.html', {
                'leave_request': leave_request,
                'notes': notes,
            })

        try:
            leave_request.provide_documents(
                handler=request.user,
                notes=notes
            )

            create_notification(
                user=leave_request.user,
                title="Δικαιολογητικά Παρασχέθηκαν",
                message=f"Τα δικαιολογητικά για την αίτησή σας για {leave_request.leave_type.name} παρασχέθηκαν και η αίτηση προχωρά στο επόμενο στάδιο",
                related_object=leave_request
            )

            if leave_request.manager_approved_by:
                create_notification(
                    user=leave_request.manager_approved_by,
                    title="Δικαιολογητικά Παρασχέθηκαν",
                    message=f"Τα δικαιολογητικά για την αίτηση του/της {leave_request.user.full_name} παρασχέθηκαν",
                    related_object=leave_request
                )

            # Αναγέννηση PDF της αίτησης για να συμπεριληφθούν τα νέα δικαιολογητικά
            try:
                from django.template.loader import render_to_string
                from weasyprint import HTML
                from django.conf import settings
                leave_request.refresh_from_db()
                private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'private_media'))
                pdf_path = os.path.join(private_media_root, 'leave_requests', str(leave_request.id), 'request.pdf')
                os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
                pdf_context = {
                    'leave_request': leave_request, 'user': leave_request.user,
                    'periods': leave_request.periods.all(),
                    'request_text': leave_request.description or '',
                    'attachments': leave_request.attachments.all(),
                    'form_data': {'description': leave_request.description, 'leave_type': leave_request.leave_type},
                }
                HTML(string=render_to_string('leaves/pdf_template.html', pdf_context)).write_pdf(pdf_path)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error regenerating PDF after providing documents: {str(e)}")
            
            success_msg = 'Τα δικαιολογητικά παρασχέθηκαν επιτυχώς! Η αίτηση επέστρεψε σε επεξεργασία.'
            if saved_count:
                success_msg += f' Αποθηκεύτηκαν {saved_count} συνημμένα αρχεία.'
            messages.success(request, success_msg)
            return redirect('leaves:leave_request_detail', pk=leave_request.pk)

        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την παροχή δικαιολογητικών: {str(e)}')
    
    # GET: Εμφάνιση σελίδας επιβεβαίωσης παροχής δικαιολογητικών
    return render(request, 'leaves/provide_documents_confirm.html', {'leave_request': leave_request})


@login_required
def acknowledge_yc_alert(request, user_id):
    """Δήλωση γνώσης για υπέρβαση αναρρωτικών — από χειριστή ή από τον ίδιο τον υπάλληλο"""
    if not request.user.is_leave_handler and request.user.pk != user_id:
        raise PermissionDenied("Δεν έχετε δικαίωμα.")
    from leaves.models import YCCommitteeAcknowledgment
    YCCommitteeAcknowledgment.objects.get_or_create(
        handler=request.user,
        employee_id=user_id
    )
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        from django.http import JsonResponse
        return JsonResponse({'success': True})
    messages.success(request, 'Η γνώση καταχωρήθηκε.')
    return redirect('leaves:handler_dashboard')


@login_required
def send_to_yc_committee(request, pk):
    """Αποστολή αίτησης σε Υγειονομική Επιτροπή — ο χειριστής ανεβάζει διαβιβαστικό"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα αποστολής σε Υγειονομική Επιτροπή.")

    leave_request = get_object_or_404(LeaveRequest, pk=pk)

    if not leave_request.can_send_to_yc:
        messages.error(request, 'Η αίτηση δεν μπορεί να σταλεί σε Υγειονομική Επιτροπή.')
        return redirect('leaves:leave_request_detail', pk=pk)

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        if not notes:
            messages.error(request, 'Απαιτούνται υποχρεωτικά σχόλια/αιτιολογία για την παραπομπή.')
            return render(request, 'leaves/yc_referral_form.html', {
                'leave_request': leave_request,
                'notes': notes,
            })

        from leaves.attachment_helpers import save_leave_request_attachments_from_request
        saved_count, upload_errors = save_leave_request_attachments_from_request(
            request, leave_request, request.user
        )
        if upload_errors:
            for err in upload_errors:
                messages.error(request, err)
            return render(request, 'leaves/yc_referral_form.html', {
                'leave_request': leave_request,
                'notes': notes,
            })
        if saved_count == 0:
            messages.error(request, 'Απαιτείται η επισύναψη του διαβιβαστικού για την Υγειονομική Επιτροπή.')
            return render(request, 'leaves/yc_referral_form.html', {
                'leave_request': leave_request,
                'notes': notes,
            })

        try:
            leave_request.send_to_yc_committee(handler=request.user, notes=notes)
            from notifications.utils import create_notification
            create_notification(
                user=leave_request.user,
                title="Παραπομπή σε Υγειονομική Επιτροπή",
                message=f"Η αίτησή σας για {leave_request.leave_type.name} παραπέμφθηκε στην Υγειονομική Επιτροπή.",
                related_object=leave_request
            )
            messages.success(request, 'Η αίτηση παραπέμφθηκε στην Υγειονομική Επιτροπή.')
            return redirect('leaves:handler_dashboard')
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Σφάλμα: {str(e)}')

    return render(request, 'leaves/yc_referral_form.html', {
        'leave_request': leave_request,
    })


@login_required
def receive_from_yc_committee(request, pk):
    """Επιστροφή από Υγειονομική Επιτροπή — ο χειριστής ανεβάζει την απόφαση"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα επιστροφής από Υγειονομική Επιτροπή.")

    leave_request = get_object_or_404(LeaveRequest, pk=pk)

    if leave_request.status != 'PENDING_YC_COMMITTEE':
        messages.error(request, 'Η αίτηση δεν είναι σε αναμονή απόφασης Υγειονομικής Επιτροπής.')
        return redirect('leaves:leave_request_detail', pk=pk)

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        if not notes:
            messages.error(request, 'Απαιτούνται υποχρεωτικά σχόλια για την απόφαση της Υγειονομικής Επιτροπής.')
            return render(request, 'leaves/yc_decision_form.html', {
                'leave_request': leave_request,
                'notes': notes,
            })

        from leaves.attachment_helpers import save_leave_request_attachments_from_request
        saved_count, upload_errors = save_leave_request_attachments_from_request(
            request, leave_request, request.user
        )
        if upload_errors:
            for err in upload_errors:
                messages.error(request, err)
            return render(request, 'leaves/yc_decision_form.html', {
                'leave_request': leave_request,
                'notes': notes,
            })
        if saved_count == 0:
            messages.error(request, 'Απαιτείται η επισύναψη της απόφασης της Υγειονομικής Επιτροπής.')
            return render(request, 'leaves/yc_decision_form.html', {
                'leave_request': leave_request,
                'notes': notes,
            })

        try:
            leave_request.receive_from_yc_committee(handler=request.user, notes=notes)
            from notifications.utils import create_notification
            create_notification(
                user=leave_request.user,
                title="Απόφαση Υγειονομικής Επιτροπής",
                message=f"Η απόφαση της Υγειονομικής Επιτροπής για την αίτησή σας για {leave_request.leave_type.name} καταχωρήθηκε.",
                related_object=leave_request
            )
            messages.success(request, 'Η απόφαση της Υγειονομικής Επιτροπής καταχωρήθηκε. Η αίτηση είναι σε επεξεργασία.')
            return redirect('leaves:handler_dashboard')
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f'Σφάλμα: {str(e)}')

    return render(request, 'leaves/yc_decision_form.html', {
        'leave_request': leave_request,
    })


@login_required
def attendance_sheet(request):
    """Παρουσιολόγιο — PDF με όλους τους υπαλλήλους Αυτοτελούς Διεύθυνσης"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Μόνο χειριστές αδειών.")
    from accounts.models import Department, User
    autotelous = Department.objects.filter(code='AUTOTELOUS_DN').first()
    departments = autotelous.get_all_sub_departments() if autotelous else []
    employees = User.objects.filter(department__in=departments, is_active=True).order_by('last_name', 'first_name')

    if request.method == 'POST':
        date_str = request.POST.get('date', '')
        if not date_str:
            messages.error(request, 'Επιλέξτε ημερομηνία.')
            return render(request, 'leaves/attendance_sheet.html', {'employees': employees, 'today': timezone.now().date()})
        from datetime import datetime
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        from django.template.loader import render_to_string
        from weasyprint import HTML

        import io
        from collections import defaultdict
        rows = []
        for emp in employees:
            leave_types_on_date = []
            for lr in LeaveRequest.objects.filter(
                user=emp,
                submitted_at__year=selected_date.year,
                status__in=['SUBMITTED', 'PENDING_PROTOCOL', 'IN_REVIEW', 'WAITING_FOR_DOCUMENTS',
                          'DECISION_PREPARATION', 'PENDING_YC_COMMITTEE', 'PENDING_SIGNATURES', 'COMPLETED']
            ).prefetch_related('periods'):
                for p in lr.periods.all():
                    if p.start_date <= selected_date <= p.end_date:
                        leave_types_on_date.append(lr.leave_type.name)
                        break
            rows.append({
                'emp': emp,
                'leave_type': ' | '.join(leave_types_on_date) if leave_types_on_date else None,
            })
        html_str = render_to_string('leaves/attendance_pdf_template.html', {
            'rows': rows,
            'selected_date': selected_date,
        })
        buf = io.BytesIO()
        HTML(string=html_str).write_pdf(buf)
        pdf = buf.getvalue()
        buf.close()
        from django.http import HttpResponse
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="parousiologio_{selected_date.strftime("%Y%m%d")}.pdf"'
        return response

    return render(request, 'leaves/attendance_sheet.html', {
        'employees': employees,
        'today': timezone.now().date(),
    })


@login_required
def return_leave_to_employee(request, pk):
    """Επιστροφή αίτησης στον αιτούντα για διόρθωση"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα επιστροφής αίτησης.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος αν η αίτηση είναι στο σωστό στάδιο
    if leave_request.status not in ['WAITING_FOR_DOCUMENTS', 'IN_REVIEW']:
        messages.error(request, 'Η αίτηση δεν μπορεί να επιστραφεί σε αυτή τη φάση.')
        return redirect('leaves:leave_request_detail', pk=leave_request.pk)
    
    if request.method == 'POST':
        return_notes = request.POST.get('return_notes', '').strip()
        
        if not return_notes:
            messages.error(request, 'Παρακαλώ συμπληρώστε την αιτιολογία επιστροφής.')
            return render(request, 'leaves/return_to_employee.html', {'leave_request': leave_request})
        
        try:
            # Επιστροφή αίτησης στον αιτούντα σε κατάσταση WAITING_FOR_DOCUMENTS
            leave_request.status = 'WAITING_FOR_DOCUMENTS'
            leave_request.return_notes = return_notes
            leave_request.returned_by = request.user
            leave_request.returned_at = timezone.now()
            leave_request.save()
            
            # Ειδοποίηση στον υπάλληλο
            create_notification(
                user=leave_request.user,
                title="Αίτηση Επιστράφηκε για Διόρθωση",
                message=f"Η αίτησή σας για {leave_request.leave_type.name} επιστράφηκε από τον χειριστή αδειών για διόρθωση ή συμπλήρωση.",
                related_object=leave_request
            )
            
            messages.success(request, 'Η αίτηση επιστράφηκε στον αιτούντα για διόρθωση!')
            return redirect('leaves:handler_dashboard')
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την επιστροφή της αίτησης: {str(e)}')
    
    # GET: Εμφάνιση σελίδας επιβεβαίωσης επιστροφής
    return render(request, 'leaves/return_to_employee.html', {'leave_request': leave_request})


@login_required
def lock_leave_request(request, pk):
    """Κλείδωμα αίτησης από χειριστή για επεξεργασία"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα κλειδώματος.")

    leave_request = get_object_or_404(LeaveRequest, pk=pk)

    if leave_request.status not in ['IN_REVIEW', 'WAITING_FOR_DOCUMENTS', 'PENDING_PROTOCOL']:
        messages.error(request, 'Η αίτηση δεν μπορεί να κλειδωθεί σε αυτή τη φάση.')
        return redirect('leaves:handler_dashboard')

    # Auto-unlock expired locks
    cutoff_time = timezone.now() - timedelta(minutes=LOCK_TIMEOUT_MINUTES)
    if leave_request.locked_at and leave_request.locked_at < cutoff_time:
        leave_request.locking_user = None
        leave_request.locked_at = None
        leave_request.save()

    # Lock the request
    leave_request.locking_user = request.user
    leave_request.locked_at = timezone.now()
    leave_request.save()

    messages.success(request, 'Η αίτηση κλειδώθηκε για επεξεργασία.')
    return redirect('leaves:leave_request_detail', pk=pk)


@login_required
def unlock_leave_request(request, pk):
    """Ξεκλείδωμα αίτησης από χειριστή"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα ξεκλειδώματος.")

    leave_request = get_object_or_404(LeaveRequest, pk=pk)

    # Only the locking user or an admin can unlock
    if leave_request.locking_user != request.user and not request.user.is_superuser:
        messages.error(request, 'Δεν μπορείτε να ξεκλειδώσετε αυτή την αίτηση.')
        return redirect('leaves:leave_request_detail', pk=pk)

    leave_request.locking_user = None
    leave_request.locked_at = None
    leave_request.save()

    messages.success(request, 'Η αίτηση ξεκλειδώθηκε.')
    return redirect('leaves:leave_request_detail', pk=pk)


@login_required
def delete_leave_request(request, pk):
    """Διαγραφή αίτησης — είτε από ιδιοκτήτη (DRAFT) είτε από χειριστή (IN_REVIEW)"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    is_owner = leave_request.user == request.user

    if is_owner and leave_request.status == 'DRAFT':
        if request.method == 'POST':
            leave_request.delete()
            messages.success(request, 'Η πρόχειρη αίτηση διαγράφηκε επιτυχώς.')
            return redirect('leaves:employee_dashboard')
        return render(request, 'leaves/delete_leave_request_confirm.html', {'leave_request': leave_request})

    if request.user.is_leave_handler:
        if leave_request.status != 'IN_REVIEW':
            messages.error(request, 'Μπορείτε να διαγράψετε μόνο αιτήσεις σε κατάσταση ΠΡΟΣ ΕΠΕΞΕΡΓΑΣΙΑ.')
            return redirect('leaves:leave_request_detail', pk=pk)

        if request.method == 'POST':
            leave_request.status = 'REJECTED_BY_LEAVES_DEPT'
            leave_request.save()
            messages.success(request, 'Η αίτηση διαγράφηκε επιτυχώς.')
            return redirect('leaves:handler_dashboard')

        return render(request, 'leaves/delete_leave_request_confirm.html', {'leave_request': leave_request})

    raise PermissionDenied("Δεν έχετε δικαίωμα διαγραφής.")


@login_required
def withdraw_completed_leave(request, pk):
    """Ανάκληση ολοκληρωμένης άδειας από τον αιτούντα"""
    leave_request = get_object_or_404(LeaveRequest, pk=pk)

    if leave_request.user != request.user:
        raise PermissionDenied("Μόνο ο αιτούντας μπορεί να ανακαλέσει την άδεια.")

    if leave_request.status != 'COMPLETED':
        messages.error(request, 'Μπορείτε να ανακαλέσετε μόνο ολοκληρωμένες άδειες.')
        return redirect('leaves:employee_dashboard')

    if request.method == 'POST':
        # Create new leave request for the revocation process
        new_request = LeaveRequest.objects.create(
            user=leave_request.user,
            leave_type=leave_request.leave_type,
            description=f'Ανάκληση άδειας #{leave_request.id}',
            status='SUBMITTED',
            parent_leave=leave_request,
            submitted_at=timezone.now()
        )

        # Copy periods
        for period in leave_request.periods.all():
            LeavePeriod.objects.create(
                leave_request=new_request,
                start_date=period.start_date,
                end_date=period.end_date
            )

        # Update original request
        leave_request.status = 'CANCELLED_BY_APPLICANT'
        leave_request.save()

        # Notify handlers
        leave_handlers = User.objects.filter(roles__code='HR_OFFICER', is_active=True).distinct()
        for handler in leave_handlers:
            create_notification(
                user=handler,
                title="Ανάκληση Ολοκληρωμένης Άδειας",
                message=f"Ο/Η {leave_request.user.full_name} ανέκαλε την ολοκληρωμένη άδεια #{leave_request.id}",
                related_object=new_request
            )

        messages.success(request, 'Η άδεια ανακλήθηκε επιτυχώς. Νέα αίτηση δημιουργήθηκε.')
        return redirect('leaves:employee_dashboard')

    return render(request, 'leaves/withdraw_completed_confirm.html', {'leave_request': leave_request})


@login_required

@login_required
def handler_upload_attachment(request, pk):
    """Μεταφόρτωση συνημμένου από χειριστή"""
    from django.conf import settings
    from django.utils import timezone
    import os
    from .crypto_utils import SecureFileHandler
    
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if request.method == 'POST' and request.FILES.get('attachment'):
        file_obj = request.FILES['attachment']
        description = request.POST.get('description', '')
        
        is_valid, error_message = SecureFileHandler.validate_file(file_obj)
        if not is_valid:
            messages.error(request, f'Αρχείο "{file_obj.name}": {error_message}')
            return redirect('leaves:leave_request_detail', pk=pk)
        
        try:
            private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                                       os.path.join(settings.BASE_DIR, 'private_media'))
            file_path = os.path.join(
                private_media_root, 'leave_requests', str(leave_request.id),
                f"handler_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{file_obj.name}"
            )
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            success, key_hex, file_size = SecureFileHandler.save_encrypted_file(file_obj, file_path)
            
            if success:
                from .models import SecureFile
                SecureFile.objects.create(
                    leave_request=leave_request,
                    original_filename=file_obj.name,
                    file_path=file_path,
                    file_size=file_size,
                    content_type=file_obj.content_type,
                    encryption_key=key_hex,
                    uploaded_by=request.user,
                    description=description
                )
                messages.success(request, f'Το αρχείο "{file_obj.name}" προστέθηκε επιτυχώς.')
            else:
                messages.error(request, 'Σφάλμα κατά την αποθήκευση του αρχείου.')
        except Exception as e:
            messages.error(request, f'Σφάλμα: {str(e)}')
    
    # Αναγέννηση PDF της αίτησης για να συμπεριληφθούν τα νέα συνημμένα
    try:
        from django.template.loader import render_to_string
        from weasyprint import HTML
        leave_request.refresh_from_db()
        pdf_path = os.path.join(
            getattr(settings, 'PRIVATE_MEDIA_ROOT', os.path.join(settings.BASE_DIR, 'private_media')),
            'leave_requests', str(leave_request.id), 'request.pdf'
        )
        os.makedirs(os.path.dirname(pdf_path), exist_ok=True)
        pdf_context = {
            'leave_request': leave_request, 'user': leave_request.user,
            'periods': leave_request.periods.all(),
            'request_text': leave_request.description or '',
            'attachments': leave_request.attachments.all(),
            'form_data': {'description': leave_request.description, 'leave_type': leave_request.leave_type},
        }
        HTML(string=render_to_string('leaves/pdf_template.html', pdf_context)).write_pdf(pdf_path)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error regenerating PDF after attachment upload: {str(e)}")
    
    return redirect('leaves:leave_request_detail', pk=pk)

def send_to_protocol_view(request, pk):
    """
    Αποστολή για Πρωτόκολλο — Δημιουργία ενοποιημένου PDF και αποστολή μέσω email.
    GET:  Εμφάνιση preview του merged PDF
    POST: Αποστολή email
    """
    # Έλεγχος δικαιωμάτων — μόνο χειριστές
    if not request.user.is_leave_handler:
        messages.error(request, 'Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.')
        return redirect('leaves:dashboard_redirect')
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Δημιουργία merged PDF (πάντα από την αρχή για να περιλαμβάνει νέα συνημμένα)
    try:
        from leaves.utils.pdf_merger import save_merged_pdf
        pdf_content, encrypted_path, key_hex = save_merged_pdf(leave_request)
        messages.success(request, 'Το ενοποιημένο PDF δημιουργήθηκε επιτυχώς.')
    except Exception as e:
        messages.error(request, f'Σφάλμα κατά τη δημιουργία του ενοποιημένου PDF: {str(e)}')
        return redirect('leaves:leave_request_detail', pk=leave_request.id)
    
    context = {
        'leave_request': leave_request,
        'merged_pdf_exists': leave_request.has_merged_pdf(),
        'merged_pdf_size': leave_request.merged_pdf_size,
        'protocol_email': getattr(settings, 'PROTOCOL_EMAIL_RECIPIENT', 'apettas@gmail.com'),
        'email_subject': None,
    }
    
    # Προβολή του email subject
    try:
        from pdede_leaves.email_utils import build_email_subject
        context['email_subject'] = build_email_subject(leave_request)
    except ImportError:
        pass
    
    if request.method == 'POST':
        try:
            from leaves.utils.pdf_merger import save_merged_pdf
            from pdede_leaves.email_utils import send_merged_pdf_email
            from leaves.crypto_utils import SecureFileHandler
            
            # Φόρτωση του αποθηκευμένου PDF
            handler = SecureFileHandler()
            pdf_content = handler.load_encrypted_file(
                leave_request.merged_pdf_path,
                leave_request.merged_pdf_encryption_key
            )
            
            if pdf_content is None:
                # Δημιουργία ξανά αν αποτυχία φόρτωσης
                pdf_content, _, _ = save_merged_pdf(leave_request)
            
            success = send_merged_pdf_email(leave_request, pdf_content)
            
            if success:
                messages.success(request, 'Το email στάλθηκε επιτυχώς!')
                context['sent_success'] = True
            else:
                messages.error(request, 'Σφάλμα κατά την αποστολή του email. Ελέγξτε τις ρυθμίσεις SMTP.')
                context['send_error'] = 'Η αποστολή απέτυχε. Επικοινωνήστε με τον διαχειριστή.'
                
        except Exception as e:
            messages.error(request, f'Σφάλμα: {str(e)}')
            context['send_error'] = str(e)
    
    return render(request, 'leaves/send_to_protocol.html', context)


@login_required
def serve_merged_pdf(request, pk):
    """
    Σερβίρισμα του ενοποιημένου PDF (κρυπτογραφημένου)
    """
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος δικαιωμάτων
    if not leave_request.can_user_view(request.user):
        messages.error(request, 'Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.')
        return redirect('leaves:dashboard_redirect')
    
    if not leave_request.has_merged_pdf():
        messages.error(request, 'Δεν υπάρχει ενοποιημένο PDF για αυτή την αίτηση.')
        return redirect('leaves:leave_request_detail', pk=leave_request.id)
    
    try:
        from leaves.crypto_utils import SecureFileHandler
        handler = SecureFileHandler()
        pdf_content = handler.load_encrypted_file(
            leave_request.merged_pdf_path,
            leave_request.merged_pdf_encryption_key
        )
        
        if pdf_content is None:
            messages.error(request, 'Δεν ήταν δυνατή η φόρτωση του ενοποιημένου PDF.')
            return redirect('leaves:leave_request_detail', pk=leave_request.id)
        
        is_download = request.GET.get('download') == '1'
        
        filename = f"merged_{leave_request.id}_{leave_request.user.full_name.replace(' ', '_')}.pdf"
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = content_disposition_header(
            as_attachment=is_download, filename=filename
        )
        return response
        
    except Exception as e:
        messages.error(request, f'Σφάλμα κατά τη φόρτωση του PDF: {str(e)}')
        return redirect('leaves:leave_request_detail', pk=leave_request.id)
