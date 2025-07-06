from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, DetailView
from django.urls import reverse_lazy
from django.http import JsonResponse, HttpResponse, Http404
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.conf import settings
import os
import mimetypes
from .models import LeaveRequest, LeavePeriod, LeaveType, SecureFile
from .forms import LeaveRequestForm
from .crypto_utils import SecureFileHandler, FileAccessController
from notifications.utils import create_notification
from django.contrib.auth import get_user_model

User = get_user_model()


class EmployeeDashboardView(LoginRequiredMixin, ListView):
    """Dashboard για όλους τους ρόλους - Προβολή των προσωπικών αιτήσεων"""
    model = LeaveRequest
    template_name = 'leaves/employee_dashboard.html'
    context_object_name = 'leave_requests'
    paginate_by = 10
    
    def get_queryset(self):
        return LeaveRequest.objects.filter(user=self.request.user).select_related(
            'leave_type', 'manager_approved_by', 'processed_by'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Στατιστικά
        context.update({
            'total_requests': self.get_queryset().count(),
            'pending_requests': self.get_queryset().filter(
                status__in=['SUBMITTED', 'APPROVED_MANAGER', 'FOR_PROTOCOL_PDEDE', 'UNDER_PROCESSING']
            ).count(),
            'completed_requests': self.get_queryset().filter(status='COMPLETED').count(),
            'rejected_requests': self.get_queryset().filter(
                status__in=['REJECTED_MANAGER', 'REJECTED_OPERATOR']
            ).count(),
        })
        
        return context


class CreateLeaveRequestView(LoginRequiredMixin, CreateView):
    """Δημιουργία νέας αίτησης άδειας"""
    model = LeaveRequest
    form_class = LeaveRequestForm
    template_name = 'leaves/create_leave_request.html'
    def get_success_url(self):
        """Ανακατεύθυνση στο κατάλληλο dashboard ανάλογα με τον ρόλο"""
        user = self.request.user
        if user.is_leave_handler:
            return reverse_lazy('leaves:handler_dashboard')
        elif user.is_department_manager:
            return reverse_lazy('leaves:manager_dashboard')
        else:
            return reverse_lazy('leaves:employee_dashboard')
    
    def form_valid(self, form):
        # Αποθηκεύουμε την αίτηση ΧΩΡΙΣ τα αρχεία προσωρινά για να έχουμε ID
        leave_request = LeaveRequest(
            user=self.request.user,
            leave_type=form.cleaned_data['leave_type'],
            description=form.cleaned_data['description'],
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
        
        return LeaveRequest.objects.filter(
            user__in=employees_to_include,
            status='SUBMITTED'
        ).select_related('user', 'leave_type').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subordinates = self.request.user.get_subordinates()
        
        # Στατιστικά
        context.update({
            'pending_approvals': self.get_queryset().count(),
            'total_subordinates': subordinates.count(),
            'approved_this_month': LeaveRequest.objects.filter(
                user__in=subordinates,
                status='APPROVED_MANAGER',
                manager_approved_at__month=timezone.now().month
            ).count(),
        })
        
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
        # Προϊστάμενοι μπορούν να εγκρίνουν αιτήσεις από το ίδιο τμήμα ή υφισταμένων
        if request.user.department and leave_request.user.department:
            # Έλεγχος αν είναι από το ίδιο τμήμα
            can_approve = (request.user.department.id == leave_request.user.department.id)
        # Ή αν είναι ο καθορισμένος manager του χρήστη
        if not can_approve and leave_request.user.manager:
            can_approve = (leave_request.user.manager == request.user)
    
    if not can_approve:
        raise PermissionDenied("Δεν μπορείτε να εγκρίνετε αυτή την αίτηση.")
    
    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        
        try:
            leave_request.approve_by_manager(request.user, comments)
            
            # Ειδοποίηση στους χειριστές αδειών
            from accounts.models import User
            leave_handlers = User.objects.filter(roles__code='HR_OFFICER', is_active=True).distinct()
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
            
            messages.success(request, 'Η αίτηση εγκρίθηκε επιτυχώς!')
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την έγκριση: {str(e)}')
    
    return redirect('leaves:manager_dashboard')


@login_required
def reject_leave_request(request, pk):
    """Απόρριψη αίτησης από προϊστάμενο"""
    if not request.user.is_department_manager:
        raise PermissionDenied("Δεν έχετε δικαίωμα απόρριψης.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος αν ο χρήστης είναι ο προϊστάμενος του αιτούντα
    if leave_request.user.manager != request.user:
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
    
    return redirect('leaves:manager_dashboard')


class HandlerDashboardView(LoginRequiredMixin, ListView):
    """Dashboard για Χειριστή Αδειών - Αιτήσεις προς επεξεργασία"""
    model = LeaveRequest
    template_name = 'leaves/handler_dashboard.html'
    context_object_name = 'leave_requests'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_leave_handler:
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Αιτήσεις που έχουν εγκριθεί από προϊστάμενο και περιμένουν επεξεργασία
        return LeaveRequest.objects.filter(
            status__in=['APPROVED_MANAGER', 'FOR_PROTOCOL_PDEDE', 'UNDER_PROCESSING']
        ).select_related('user', 'leave_type', 'manager_approved_by').order_by('-manager_approved_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Στατιστικά
        context.update({
            'pending_processing': self.get_queryset().count(),
            'processed_this_month': LeaveRequest.objects.filter(
                status='COMPLETED',
                processed_at__month=timezone.now().month
            ).count(),
            'total_completed': LeaveRequest.objects.filter(status='COMPLETED').count(),
            # Στατιστικά για ΣΗΔΕ workflows
            'for_protocol_count': LeaveRequest.objects.filter(
                status='FOR_PROTOCOL_PDEDE'
            ).count(),
            'under_processing_count': LeaveRequest.objects.filter(
                status='UNDER_PROCESSING'
            ).count(),
        })
        
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
        if self.request.user.is_leave_handler:
            # Χειριστής αδειών βλέπει όλους τους χρήστες
            return User.objects.select_related('department').order_by('last_name', 'first_name')
        elif self.request.user.is_department_manager:
            # Προϊστάμενος βλέπει χρήστες του τμήματός του και όλων των υποτμημάτων
            if self.request.user.department:
                # Βρίσκω όλα τα τμήματα (το δικό του και όλα τα υποτμήματα)
                all_departments = self.request.user.department.get_all_sub_departments()
                
                # Επιστρέφω χρήστες από όλα αυτά τα τμήματα
                return User.objects.filter(
                    department__in=all_departments
                ).select_related('department').order_by('last_name', 'first_name')
            else:
                # Αν δεν έχει τμήμα, δεν βλέπει κανέναν
                return User.objects.none()
        return User.objects.none()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Στατιστικά ανάλογα με τον ρόλο
        if self.request.user.is_leave_handler:
            # Στατιστικά για όλους τους χρήστες
            context.update({
                'total_users': User.objects.count(),
                'active_users': User.objects.filter(is_active=True).count(),
                'employees': User.objects.filter(roles__code='employee').distinct().count(),
                'managers': User.objects.filter(roles__code='department_manager').distinct().count(),
                'user_role': 'handler'
            })
        elif self.request.user.is_department_manager:
            # Στατιστικά για το τμήμα του προϊσταμένου και όλα τα υποτμήματα
            if self.request.user.department:
                # Βρίσκω όλα τα τμήματα (το δικό του και όλα τα υποτμήματα)
                all_departments = self.request.user.department.get_all_sub_departments()
                department_users = User.objects.filter(department__in=all_departments)
                
                context.update({
                    'total_users': department_users.count(),
                    'active_users': department_users.filter(is_active=True).count(),
                    'employees': department_users.filter(roles__code='employee').distinct().count(),
                    'managers': department_users.filter(roles__code='department_manager').distinct().count(),
                    'user_role': 'manager',
                    'department_name': self.request.user.department.name
                })
            else:
                context.update({
                    'total_users': 0,
                    'active_users': 0,
                    'employees': 0,
                    'managers': 0,
                    'user_role': 'manager',
                    'department_name': 'Άγνωστο'
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
            'pending_requests': all_requests.filter(status__in=['SUBMITTED', 'APPROVED_MANAGER', 'UNDER_PROCESSING']).count(),
            'rejected_requests': all_requests.filter(status__in=['REJECTED_MANAGER', 'REJECTED_OPERATOR']).count(),
            'total_days_used': sum(req.total_days for req in all_requests.filter(status='COMPLETED')),
            'user_role': 'handler' if self.request.user.is_leave_handler else 'manager'
        })
        
        return context


@login_required
def complete_leave_request(request, pk):
    """Ολοκλήρωση αίτησης από χειριστή αδειών"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα ολοκλήρωσης.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        protocol_number = request.POST.get('protocol_number', '')
        
        try:
            # Ενημέρωση πρωτοκόλλου αν υπάρχει
            if protocol_number:
                leave_request.protocol_number = protocol_number
                leave_request.save()
            
            leave_request.complete_by_handler(request.user, comments)
            
            # Ειδοποίηση στον υπάλληλο
            create_notification(
                user=leave_request.user,
                title="Αίτηση Ολοκληρώθηκε",
                message=f"Η αίτησή σας για {leave_request.leave_type.name} ολοκληρώθηκε επιτυχώς",
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
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        try:
            leave_request.reject_by_handler(request.user, reason)
            
            # Ειδοποίηση στον υπάλληλο
            create_notification(
                user=leave_request.user,
                title="Αίτηση Απορρίφθηκε",
                message=f"Η αίτησή σας για {leave_request.leave_type.name} απορρίφθηκε από τον χειριστή αδειών",
                related_object=leave_request
            )
            
            messages.success(request, 'Η αίτηση απορρίφθηκε επιτυχώς!')
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την απόρριψη: {str(e)}')
    
    return redirect('leaves:handler_dashboard')


@login_required
def send_to_protocol_pdede(request, pk):
    """Στέλνει την αίτηση για πρωτόκολλο στο ΣΗΔΕ"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα επεξεργασίας.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if leave_request.status != 'APPROVED_MANAGER':
        messages.error(request, 'Η αίτηση δεν μπορεί να σταλεί για πρωτόκολλο σε αυτή τη φάση.')
        return redirect('leaves:handler_dashboard')
    
    if request.method == 'POST':
        try:
            # Αλλαγή status σε FOR_PROTOCOL_PDEDE
            leave_request.status = 'FOR_PROTOCOL_PDEDE'
            leave_request.processed_by = request.user
            leave_request.processed_at = timezone.now()
            leave_request.save()
            
            # Ειδοποίηση στον υπάλληλο (προσωρινά απενεργοποιημένη)
            try:
                create_notification(
                    user=leave_request.user,
                    title="Αίτηση στάλθηκε για Πρωτόκολλο",
                    message=f"Η αίτησή σας για {leave_request.leave_type.name} στάλθηκε στο ΣΗΔΕ για πρωτοκόλληση",
                    related_object=leave_request
                )
            except Exception as notification_error:
                # Αν αποτύχει το notification, συνεχίζουμε χωρίς να διακόπτουμε τη διαδικασία
                print(f"Notification error: {notification_error}")
            
            messages.success(request, 'Η αίτηση στάλθηκε επιτυχώς για πρωτόκολλο στο ΣΗΔΕ!')
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την αποστολή: {str(e)}')
    
    return redirect('leaves:handler_dashboard')


@login_required
def upload_protocol_pdf(request, pk):
    """Ανέβασμα του πρωτοκολλημένου PDF από το ΣΗΔΕ"""
    if not request.user.is_leave_handler:
        raise PermissionDenied("Δεν έχετε δικαίωμα επεξεργασίας.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if leave_request.status != 'FOR_PROTOCOL_PDEDE':
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
                leave_request.status = 'UNDER_PROCESSING'
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
                    # Αν αποτύχει το notification, συνεχίζουμε χωρίς να διακόπτουμε τη διαδικασία
                    print(f"Notification error: {notification_error}")
                
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
            user.is_leave_handler or  # Χειριστής αδειών
            user.is_administrator  # Διαχειριστής
        )
        
        if not can_view:
            raise PermissionDenied("Δεν έχετε δικαίωμα προβολής αυτής της αίτησης.")
        
        return obj
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Προσθήκη attachments στο context
        attachments = self.object.attachments.all()
        context['attachments'] = attachments
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
                success=False
            )
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτό το αρχείο.")
        
        # Φόρτωση και αποκρυπτογράφηση του αρχείου
        decrypted_content = SecureFileHandler.load_encrypted_file(
            secure_file.file_path,
            secure_file.encryption_key
        )
        
        if decrypted_content is None:
            # Log του σφάλματος
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to decrypt file {file_id} for user {request.user.id}")
            raise Http404("Το αρχείο δεν μπορεί να φορτωθεί.")
        
        # Καταγραφή επιτυχούς πρόσβασης
        FileAccessController.log_file_access(
            user=request.user,
            secure_file=secure_file,
            success=True
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
            
            # Αλλάζουμε την κατάσταση σε SUBMITTED
            leave_request.status = 'SUBMITTED'
            leave_request.submitted_at = timezone.now()
            leave_request.save()
            
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
    from django.http import HttpResponse, Http404
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
            request.user.is_leave_handler):
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
            # If download parameter is set, force download, otherwise inline view
            if request.GET.get('download'):
                response['Content-Disposition'] = f'attachment; filename=leave_request_{leave_request.id}.pdf'
            else:
                response['Content-Disposition'] = f'inline; filename=leave_request_{leave_request.id}.pdf'
            return response
    except Exception:
        raise Http404("Σφάλμα κατά τη λήψη του PDF")
