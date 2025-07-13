from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from .models import User, Role, Department
from .forms import UserRegistrationForm



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
                
                # Αν είναι προϊστάμενος ΚΕΔΑΣΥ/ΚΕΠΕΑ, προσθέτουμε και τα στατιστικά πρωτοκόλλου
                if (user.department and user.department.department_type and
                    user.department.department_type.code in ['KEDASY', 'KEPEA']):
                    from django.db.models import Q
                    context['is_kedasy_kepea_manager'] = True
                    context['kedasy_kepea_pending_protocol_count'] = LeaveRequest.objects.filter(
                        status='PENDING_KEDASY_KEPEA_PROTOCOL'
                    ).count()
                
            elif user.is_leave_handler:
                context['pending_processing'] = LeaveRequest.objects.filter(
                    status='APPROVED_MANAGER'
                ).count()
                
            elif user.is_secretary:
                context['pending_kedasy_kepea_protocol'] = LeaveRequest.objects.filter(
                    status='PENDING_KEDASY_KEPEA_PROTOCOL'
                ).count()
        except ImportError:
            # Αν το leaves app δεν είναι διαθέσιμο ακόμα
            pass
        
        # Υπολογισμός υπολοίπων αδειών
        try:
            user.update_leave_balance()
            leave_balance = user.get_leave_balance_breakdown()
            context['leave_balance'] = leave_balance
            
            # Υπολογισμός percentages για progress bar
            total_days = leave_balance.get('total_days', 0)
            if total_days > 0:
                carryover_percentage = (leave_balance.get('carryover_days', 0) / total_days) * 100
                current_year_percentage = (leave_balance.get('current_year_days', 0) / total_days) * 100
            else:
                carryover_percentage = 0
                current_year_percentage = 0
                
            context['carryover_percentage'] = carryover_percentage
            context['current_year_percentage'] = current_year_percentage
        except Exception as e:
            # Fallback values σε περίπτωση σφάλματος
            context['leave_balance'] = {
                'carryover_days': 0,
                'current_year_days': 0,
                'total_days': 0,
                'annual_entitlement': 0
            }
            context['carryover_percentage'] = 0
            context['current_year_percentage'] = 0
        
        return context


def login_view(request):
    """Login view με έλεγχο registration status"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        if user is not None:
            # Έλεγχος αν ο χρήστης μπορεί να έχει πρόσβαση στο σύστημα
            if user.can_access_system():
                login(request, user)
                return redirect('accounts:dashboard')
            else:
                # Ο χρήστης είναι PENDING ή REJECTED
                if user.registration_status == 'PENDING':
                    messages.warning(request, 
                        'Η εγγραφή σας είναι σε εκκρεμότητα. Παρακαλώ περιμένετε την έγκριση από τον χειριστή αδειών.')
                elif user.registration_status == 'REJECTED':
                    messages.error(request, 
                        'Η εγγραφή σας έχει απορριφθεί. Παρακαλώ επικοινωνήστε με το διαχειριστή.')
                else:
                    messages.error(request, 
                        'Δεν έχετε δικαίωμα πρόσβασης στο σύστημα.')
        else:
            messages.error(request, 'Λάθος email ή κωδικός πρόσβασης.')
    
    return render(request, 'accounts/login.html')


def logout_view(request):
    """Logout view"""
    logout(request)
    messages.info(request, 'Αποσυνδεθήκατε επιτυχώς.')
    return redirect('accounts:login')


def register_view(request):
    """Εγγραφή νέων χρηστών"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        
        # DEBUG: Εκτύπωση των δεδομένων που λαμβάνονται
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"DEBUG: POST data received: {request.POST}")
        logger.error(f"DEBUG: Form data: {form.data}")
        logger.error(f"DEBUG: Form is_valid: {form.is_valid()}")
        
        if not form.is_valid():
            logger.error(f"DEBUG: Form errors: {form.errors}")
        
        if form.is_valid():
            try:
                user = form.save()
                logger.error(f"DEBUG: User created successfully: {user.email}")
                messages.success(request,
                    f'Η εγγραφή σας ολοκληρώθηκε επιτυχώς! '
                    f'Η αίτησή σας στάλθηκε για έγκριση. '
                    f'Θα ενημερωθείτε όταν εγκριθεί η πρόσβασή σας στο σύστημα.')
                return redirect('accounts:registration_pending')
            except Exception as e:
                logger.error(f"DEBUG: Error saving user: {e}")
                messages.error(request, f'Σφάλμα κατά την εγγραφή: {e}')
        else:
            # Προσθήκη errors στα messages για debugging
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'accounts/register.html', {'form': form})


def registration_pending_view(request):
    """Σελίδα επιβεβαίωσης εγγραφής"""
    return render(request, 'accounts/registration_pending.html')


def registration_status_view(request):
    """Έλεγχος κατάστασης εγγραφής"""
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            context = {
                'user': user,
                'status_found': True
            }
        except User.DoesNotExist:
            context = {
                'status_found': False,
                'email': email
            }
    else:
        context = {'status_found': None}
    
    return render(request, 'accounts/registration_status.html', context)


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
        
        # Φιλτράρισμα χρηστών βάσει ρόλου
        if self.request.user.is_superuser:
            # Superuser βλέπει όλους
            users = User.objects.select_related('department').prefetch_related('roles')
        elif self.request.user.is_administrator:
            # Administrator βλέπει όλους
            users = User.objects.select_related('department').prefetch_related('roles')
        elif self.request.user.is_department_manager:
            # Department manager βλέπει μόνο τους χρήστες του τμήματός του και των υποτμημάτων
            subordinates = self.request.user.get_subordinates()
            users = subordinates.select_related('department').prefetch_related('roles')
        elif self.request.user.is_leave_handler:
            # Leave handler βλέπει όλους (χρειάζεται για διαχείριση αδειών)
            users = User.objects.select_related('department').prefetch_related('roles')
        else:
            # Άλλοι χρήστες δεν βλέπουν κανέναν
            users = User.objects.none()
        
        context['users'] = users.order_by('last_name', 'first_name')
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