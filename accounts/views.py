from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from .models import User, Role, Department


class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard για όλους τους χρήστες"""
    template_name = 'accounts/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Βασικές πληροφορίες χρήστη
        context['user'] = user
        context['user_roles'] = user.get_role_names()
        
        try:
            # Εισαγωγή μοντέλων leaves μόνο αν είναι διαθέσιμα
            from leaves.models import LeaveRequest
            
            if user.has_role('employee'):
                context['my_requests_count'] = LeaveRequest.objects.filter(user=user).count()
                context['pending_requests_count'] = LeaveRequest.objects.filter(
                    user=user,
                    status__in=['SUBMITTED', 'APPROVED_MANAGER']
                ).count()
                
            elif user.is_department_manager:
                subordinates = user.get_subordinates()
                context['pending_approvals'] = LeaveRequest.objects.filter(
                    user__in=subordinates,
                    status='SUBMITTED'
                ).count()
                
            elif user.is_leave_handler:
                context['pending_processing'] = LeaveRequest.objects.filter(
                    status='APPROVED_MANAGER'
                ).count()
        except ImportError:
            # Αν το leaves app δεν είναι διαθέσιμο ακόμα
            pass
        
        return context


def login_view(request):
    """View για login"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    from django.contrib.auth import authenticate, login
    from django.contrib import messages
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next', 'accounts:dashboard')
            return redirect(next_url)
        else:
            messages.error(request, 'Λάθος όνομα χρήστη ή κωδικός.')
    
    return render(request, 'accounts/login.html')


@login_required  
def logout_view(request):
    """View για logout"""
    from django.contrib.auth import logout
    logout(request)
    return redirect('accounts:login')


class UserRoleManagementView(LoginRequiredMixin, TemplateView):
    """Διαχείριση ρόλων χρηστών"""
    template_name = 'accounts/user_role_management.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Μόνο administrators μπορούν να διαχειρίζονται ρόλους
        if not request.user.is_administrator:
            raise PermissionDenied("Δεν έχετε δικαίωμα διαχείρισης ρόλων.")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users'] = User.objects.select_related('department').prefetch_related('roles').order_by('last_name', 'first_name')
        context['all_roles'] = Role.objects.filter(is_active=True).order_by('name')
        context['departments'] = Department.objects.filter(is_active=True).order_by('name')
        return context


@login_required
def assign_role(request):
    """AJAX view για ανάθεση/αφαίρεση ρόλου"""
    if not request.user.is_administrator:
        return JsonResponse({'success': False, 'error': 'Δεν έχετε δικαίωμα διαχείρισης ρόλων.'})
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role_code = request.POST.get('role_code')
        action = request.POST.get('action')  # 'add' ή 'remove'
        
        try:
            user = User.objects.get(pk=user_id)
            role = Role.objects.get(code=role_code)
            
            if action == 'add':
                user.roles.add(role)
                message = f'Ο ρόλος "{role.name}" προστέθηκε στον χρήστη {user.full_name}'
            elif action == 'remove':
                user.roles.remove(role)
                message = f'Ο ρόλος "{role.name}" αφαιρέθηκε από τον χρήστη {user.full_name}'
            else:
                return JsonResponse({'success': False, 'error': 'Μη έγκυρη ενέργεια'})
            
            return JsonResponse({
                'success': True, 
                'message': message,
                'user_roles': user.get_role_names()
            })
            
        except (User.DoesNotExist, Role.DoesNotExist) as e:
            return JsonResponse({'success': False, 'error': 'Χρήστης ή ρόλος δεν βρέθηκε'})
    
    return JsonResponse({'success': False, 'error': 'Μη έγκυρο αίτημα'})


@login_required
def update_user_department(request):
    """AJAX view για ενημέρωση τμήματος χρήστη"""
    if not request.user.is_administrator:
        return JsonResponse({'success': False, 'error': 'Δεν έχετε δικαίωμα διαχείρισης χρηστών.'})
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        department_id = request.POST.get('department_id')
        
        try:
            user = User.objects.get(pk=user_id)
            
            if department_id:
                department = Department.objects.get(pk=department_id)
                user.department = department
                message = f'Ο χρήστης {user.full_name} μετακινήθηκε στο τμήμα "{department.name}"'
            else:
                user.department = None
                message = f'Ο χρήστης {user.full_name} αφαιρέθηκε από όλα τα τμήματα'
            
            user.save()
            
            return JsonResponse({
                'success': True,
                'message': message,
                'department_name': user.department.name if user.department else 'Χωρίς τμήμα'
            })
            
        except (User.DoesNotExist, Department.DoesNotExist) as e:
            return JsonResponse({'success': False, 'error': 'Χρήστης ή τμήμα δεν βρέθηκε'})
    
    return JsonResponse({'success': False, 'error': 'Μη έγκυρο αίτημα'})