from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import User


def login_view(request):
    """Σελίδα σύνδεσης"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if user.is_active:
                login(request, user)
                messages.success(request, f'Καλώς ήρθες, {user.full_name}!')
                next_url = request.GET.get('next', 'accounts:dashboard')
                return redirect(next_url)
            else:
                messages.error(request, 'Ο λογαριασμός σας δεν είναι ενεργός.')
        else:
            messages.error(request, 'Λάθος στοιχεία σύνδεσης.')
    
    return render(request, 'accounts/login.html')


def logout_view(request):
    """Αποσύνδεση χρήστη"""
    logout(request)
    messages.info(request, 'Αποσυνδεθήκατε επιτυχώς.')
    return redirect('accounts:login')


class DashboardView(LoginRequiredMixin, TemplateView):
    """Κεντρική σελίδα ανάλογα με τον ρόλο του χρήστη"""
    template_name = 'accounts/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context.update({
            'user_role': user.role,
            'user_full_name': user.full_name,
            'department_name': user.department.name if user.department else 'Δεν έχει ανατεθεί',
        })
        
        # Προσθήκη στατιστικών ανάλογα με τον ρόλο
        try:
            from leaves.models import LeaveRequest
            
            if user.role == 'employee':
                context['my_requests_count'] = LeaveRequest.objects.filter(user=user).count()
                context['pending_requests_count'] = LeaveRequest.objects.filter(
                    user=user,
                    status__in=['SUBMITTED', 'APPROVED_MANAGER']
                ).count()
                
            elif user.is_department_manager():
                subordinates = user.get_subordinates()
                context['pending_approvals'] = LeaveRequest.objects.filter(
                    user__in=subordinates,
                    status='SUBMITTED'
                ).count()
                
            elif user.is_leave_handler():
                context['pending_processing'] = LeaveRequest.objects.filter(
                    status='APPROVED_MANAGER'
                ).count()
        except ImportError:
            # Αν το leaves app δεν είναι διαθέσιμο ακόμα
            pass
        
        return context