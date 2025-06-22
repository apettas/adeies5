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
from .models import LeaveRequest, LeaveType, SecureFile
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
        elif user.is_department_manager():
            return reverse_lazy('leaves:manager_dashboard')
        else:
            return reverse_lazy('leaves:employee_dashboard')
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.status = 'SUBMITTED'
        form.instance.submitted_at = timezone.now()
        
        response = super().form_valid(form)
        
        # Επεξεργασία επισυναπτόμενων αρχείων
        self._handle_file_uploads(form)
        
        # Αποστολή ειδοποίησης στον προϊστάμενο (αν υπάρχει)
        user = self.request.user
        if hasattr(user, 'manager') and user.manager:
            create_notification(
                user=user.manager,
                title="Νέα Αίτηση Άδειας",
                message=f"Ο/Η {user.full_name} υπέβαλε αίτηση άδειας για {form.instance.leave_type.name}",
                related_object=self.object
            )
        elif user.is_department_manager or user.is_leave_handler:
            # Για προϊσταμένους και χειριστές αδειών που δεν έχουν manager,
            # στέλνουμε ειδοποίηση στον διαχειριστή ή άλλον ανώτερο
            try:
                from accounts.models import User
                admins = User.objects.filter(role='admin').first()
                if admins:
                    create_notification(
                        user=admins,
                        title="Νέα Αίτηση Άδειας - Στέλεχος",
                        message=f"Ο/Η {user.full_name} ({user.get_role_display()}) υπέβαλε αίτηση άδειας για {form.instance.leave_type.name}",
                        related_object=self.object
                    )
            except Exception:
                pass  # Σιωπηλή αποτυχία αν δεν υπάρχει διαχειριστής
        
        messages.success(self.request, 'Η αίτησή σας υποβλήθηκε επιτυχώς!')
        return response
    
    def _handle_file_uploads(self, form):
        """Επεξεργασία και κρυπτογραφημένη αποθήκευση αρχείου"""
        file_obj = form.cleaned_data.get('attachment')
        
        if not file_obj:
            return
        
        private_media_root = getattr(settings, 'PRIVATE_MEDIA_ROOT',
                                   os.path.join(settings.BASE_DIR, 'private_media'))
        
        try:
            # Δημιουργία unique file path
            file_path = os.path.join(
                private_media_root,
                'leave_requests',
                str(self.object.id),
                f"{timezone.now().strftime('%Y%m%d_%H%M%S')}_{file_obj.name}"
            )
            
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
                    uploaded_by=self.request.user
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
            logger.error(f"Error handling file upload: {str(e)}")
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
        if not request.user.is_department_manager():
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Αιτήσεις των υφισταμένων που περιμένουν έγκριση
        subordinates = self.request.user.get_subordinates()
        employees_to_include = list(subordinates)
        
        # Αν ο χρήστης είναι ο ανώτερος προϊστάμενος, προσθέτουμε και αιτήσεις
        # από άλλους προϊσταμένους/χειριστές που δεν έχουν manager
        if self.request.user.is_department_manager():
            from accounts.models import User
            orphan_managers = User.objects.filter(
                Q(role='manager') | Q(role='handler'),
                manager__isnull=True,
                department=self.request.user.department
            ).exclude(pk=self.request.user.pk)
            
            employees_to_include.extend(list(orphan_managers))
        
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
    """Έγκριση αίτησης από προϊστάμενο"""
    if not request.user.is_department_manager():
        raise PermissionDenied("Δεν έχετε δικαίωμα έγκρισης.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος αν ο χρήστης είναι ο προϊστάμενος του αιτούντα
    if leave_request.user.manager != request.user:
        raise PermissionDenied("Δεν μπορείτε να εγκρίνετε αυτή την αίτηση.")
    
    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        
        try:
            leave_request.approve_by_manager(request.user, comments)
            
            # Ειδοποίηση στους χειριστές αδειών
            from accounts.models import User
            leave_handlers = User.objects.filter(role='leave_handler', is_active=True)
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
    if not request.user.is_department_manager():
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
            status='APPROVED_MANAGER'
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
        })
        
        return context


class UsersListView(LoginRequiredMixin, ListView):
    """Λίστα όλων των χρηστών για χειριστή αδειών"""
    model = User
    template_name = 'leaves/users_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_leave_handler:
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.select_related('department').order_by('last_name', 'first_name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Στατιστικά
        context.update({
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'employees': User.objects.filter(role='employee').count(),
            'managers': User.objects.filter(role='department_manager').count(),
        })
        
        return context


class UserLeaveHistoryView(LoginRequiredMixin, ListView):
    """Ιστορικό αδειών συγκεκριμένου χρήστη"""
    model = LeaveRequest
    template_name = 'leaves/user_leave_history.html'
    context_object_name = 'leave_requests'
    paginate_by = 10
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_leave_handler:
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
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
            (user.is_department_manager() and obj.user.manager == user) or  # Ο προϊστάμενός του
            user.is_leave_handler or  # Χειριστής αδειών
            user.is_administrator()  # Διαχειριστής
        )
        
        if not can_view:
            raise PermissionDenied("Δεν έχετε δικαίωμα προβολής αυτής της αίτησης.")
        
        return obj


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