from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, DetailView
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from .models import LeaveRequest, LeaveType, LeaveRequestDocument
from .forms import LeaveRequestForm
from notifications.utils import create_notification


class EmployeeDashboardView(LoginRequiredMixin, ListView):
    """Dashboard για Υπάλληλο - Προβολή των αιτήσεών του"""
    model = LeaveRequest
    template_name = 'leaves/employee_dashboard.html'
    context_object_name = 'leave_requests'
    paginate_by = 10
    
    def get_queryset(self):
        return LeaveRequest.objects.filter(employee=self.request.user).select_related(
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
    success_url = reverse_lazy('leaves:employee_dashboard')
    
    def form_valid(self, form):
        form.instance.employee = self.request.user
        form.instance.status = 'SUBMITTED'
        response = super().form_valid(form)
        
        # Αποστολή ειδοποίησης στον προϊστάμενο
        if self.request.user.manager:
            create_notification(
                user=self.request.user.manager,
                title="Νέα Αίτηση Άδειας",
                message=f"Ο/Η {self.request.user.full_name} υπέβαλε αίτηση άδειας για {form.instance.leave_type.name}",
                related_object=self.object
            )
        
        messages.success(self.request, 'Η αίτησή σας υποβλήθηκε επιτυχώς!')
        return response


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
        return LeaveRequest.objects.filter(
            employee__in=subordinates,
            status='SUBMITTED'
        ).select_related('employee', 'leave_type').order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subordinates = self.request.user.get_subordinates()
        
        # Στατιστικά
        context.update({
            'pending_approvals': self.get_queryset().count(),
            'total_subordinates': subordinates.count(),
            'approved_this_month': LeaveRequest.objects.filter(
                employee__in=subordinates,
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
    if leave_request.employee.manager != request.user:
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
                    message=f"Η αίτηση του/της {leave_request.employee.full_name} εγκρίθηκε και περιμένει επεξεργασία",
                    related_object=leave_request
                )
            
            # Ειδοποίηση στον υπάλληλο
            create_notification(
                user=leave_request.employee,
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
    if leave_request.employee.manager != request.user:
        raise PermissionDenied("Δεν μπορείτε να απορρίψετε αυτή την αίτηση.")
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        try:
            leave_request.reject_by_manager(request.user, reason)
            
            # Ειδοποίηση στον υπάλληλο
            create_notification(
                user=leave_request.employee,
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
        if not request.user.is_leave_handler():
            raise PermissionDenied("Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # Αιτήσεις που έχουν εγκριθεί από προϊστάμενο και περιμένουν επεξεργασία
        return LeaveRequest.objects.filter(
            status='APPROVED_MANAGER'
        ).select_related('employee', 'leave_type', 'manager_approved_by').order_by('-manager_approved_at')
    
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


@login_required
def complete_leave_request(request, pk):
    """Ολοκλήρωση αίτησης από χειριστή αδειών"""
    if not request.user.is_leave_handler():
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
                user=leave_request.employee,
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
    if not request.user.is_leave_handler():
        raise PermissionDenied("Δεν έχετε δικαίωμα απόρριψης.")
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        
        try:
            leave_request.reject_by_handler(request.user, reason)
            
            # Ειδοποίηση στον υπάλληλο
            create_notification(
                user=leave_request.employee,
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
            obj.employee == user or  # Ο ίδιος ο αιτών
            (user.is_department_manager() and obj.employee.manager == user) or  # Ο προϊστάμενός του
            user.is_leave_handler() or  # Χειριστής αδειών
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
    
    if user.is_leave_handler():
        return redirect('leaves:handler_dashboard')
    elif user.is_department_manager():
        return redirect('leaves:manager_dashboard')
    else:
        return redirect('leaves:employee_dashboard')