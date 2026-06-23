from django.shortcuts import render, redirect, get_object_or_404
from urllib.parse import quote

from django.contrib.auth import authenticate, login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import TemplateView, FormView
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.conf import settings
from .models import User, Role, Department, normalize_person_name_lower, resolve_specialty_from_gsn_branch
from .forms import UserRegistrationForm, CompleteSSORegistrationForm
from notifications.utils import create_notification
from pdede_leaves.email_utils import send_registration_approved_email



class CompleteSSORegistrationView(FormView):
    """
    View για συμπλήρωση στοιχείων από νέο SSO χρήστη.
    Ο χρήστης έχει δημιουργηθεί από το CAS αλλά είναι PENDING χωρίς στοιχεία.
    """
    template_name = 'accounts/complete_sso_registration.html'
    form_class = CompleteSSORegistrationForm

    def dispatch(self, request, *args, **kwargs):
        # Ο χρήστης μπορεί να είναι είτε anonymous (με email query param)
        # είτε logged in αλλά PENDING
        self.target_email = (
            request.GET.get('email')
            or request.POST.get('email')
            or ''
        )
        if request.user.is_authenticated:
            self.target_email = request.user.email
        if not self.target_email:
            messages.error(request, 'Δεν βρέθηκε ο λογαριασμός σας. Παρακαλώ κάντε σύνδεση μέσω ΠΣΔ.')
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['target_email'] = self.target_email
        return context

    def get_initial(self):
        initial = super().get_initial()
        try:
            user = User.objects.get(email=self.target_email)
            initial['email'] = user.email
            initial['first_name'] = normalize_person_name_lower(user.first_name)
            initial['last_name'] = normalize_person_name_lower(user.last_name)
            initial['father_name'] = normalize_person_name_lower(user.father_name)
            initial['name_accusative'] = normalize_person_name_lower(user.name_accusative)
            initial['employee_number'] = user.employee_number
            initial['gsn_branch'] = user.gsn_branch
            initial['sso_organizational_unit'] = user.sso_organizational_unit
            initial['role_description'] = user.role_description
            if user.specialty_id:
                initial['specialty'] = user.specialty_id
            elif user.gsn_branch:
                specialty = resolve_specialty_from_gsn_branch(user.gsn_branch)
                if specialty:
                    initial['specialty'] = specialty.pk
        except User.DoesNotExist:
            pass
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['target_email'] = self.target_email
        return kwargs

    def form_valid(self, form):
        try:
            user = User.objects.get(email=self.target_email)
            user.first_name = form.cleaned_data['first_name']
            user.last_name = form.cleaned_data['last_name']
            user.name_accusative = form.cleaned_data['name_accusative']
            user.department = form.cleaned_data['department']
            user.specialty = form.cleaned_data['specialty']
            user.phone1 = form.cleaned_data.get('phone', '')
            user.father_name = form.cleaned_data.get('father_name', '')
            user.employee_number = form.cleaned_data.get('employee_number') or None
            user.gsn_branch = form.cleaned_data.get('gsn_branch', '')
            user.sso_organizational_unit = form.cleaned_data.get('sso_organizational_unit', '')
            user.gender = form.cleaned_data.get('gender', '')
            user.role_description = form.cleaned_data.get('role_description', '')
            # Παραμένει PENDING — θα το εγκρίνει ο χειριστής
            user.save()

            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"SSO user completed registration: {user.email}")

            # Αποσύνδεση για να μην έχει πρόσβαση πριν την έγκριση
            auth_logout(self.request)

            messages.success(self.request,
                'Τα στοιχεία σας καταχωρήθηκαν επιτυχώς! '
                'Η αίτησή σας στάλθηκε για έγκριση. '
                'Θα ενημερωθείτε στο email σας όταν ενεργοποιηθεί ο λογαριασμός σας.')
            return redirect('accounts:registration_pending')
        except User.DoesNotExist:
            messages.error(self.request, 'Σφάλμα: Ο λογαριασμός σας δεν βρέθηκε.')
            return redirect('accounts:login')


class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard για όλους τους χρήστες"""
    template_name = 'accounts/dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        # Αν ο χρήστης είναι PENDING, ανακατεύθυνση στη σελίδα εκκρεμότητας
        if request.user.is_pending_approval:
            return redirect('accounts:registration_pending')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Βασικές πληροφορίες χρήστη
        context['user'] = user
        context['user_roles'] = user.get_role_names()
        
        try:
            # Εισαγωγή μοντέλων leaves μόνο αν είναι διαθέσιμα
            from leaves.models import LeaveRequest
            
            if user.is_employee:
                context['my_requests_count'] = LeaveRequest.objects.filter(user=user).count()
                context['pending_requests_count'] = LeaveRequest.objects.filter(
                    user=user,
                    status__in=['SUBMITTED', 'PENDING_PROTOCOL']
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
                        status='PENDING_KEDASY_PROTOCOL'
                    ).count()
                
            elif user.is_leave_handler:
                context['pending_processing'] = LeaveRequest.objects.filter(
                    status='PENDING_PROTOCOL'
                ).count()
                
            elif user.is_secretary:
                context['pending_kedasy_kepea_protocol'] = LeaveRequest.objects.filter(
                    status='PENDING_KEDASY_PROTOCOL'
                ).count()
        except ImportError:
            # Αν το leaves app δεν είναι διαθέσιμο ακόμα
            pass
        
        # Υπολογισμός υπολοίπων αδειών
        try:
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
    """Login view με έλεγχο registration status και CAS option"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    from django.conf import settings
    cas_enabled = getattr(settings, 'CAS_ENABLED', False)
    
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        user = authenticate(request, username=email, password=password)
        if user is not None:
            if user.can_access_system():
                login(request, user)
                return redirect('accounts:dashboard')
            else:
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
    
    return render(request, 'accounts/login.html', {'cas_enabled': cas_enabled})


from django_cas_ng.views import LoginView as CASLoginView


class PdedeCASLoginView(CASLoginView):
    """CAS login — new CAS users go through registration workflow"""

    def successful_login(self, request, next_page):
        user = request.user
        # Νέος χρήστης από CAS: χωρίς registration_status → PENDING
        if not user.registration_status or user.registration_status == 'PENDING':
            user.registration_status = 'PENDING'
            user.is_active = False
            user.save()

            email = user.email

            # Αποσύνδεση για να μην έχει πρόσβαση ακόμα
            auth_logout(request)

            complete_url = (
                reverse('accounts:complete_sso_registration')
                + f'?email={quote(email, safe="")}'
            )
            return redirect(complete_url)

        # Εγκεκριμένος χρήστης → κανονική σύνδεση
        return super().successful_login(request, next_page)


def _cas_service_url(request, path):
    """Δημόσιο HTTPS URL για CAS service parameter."""
    root = getattr(settings, 'CAS_ROOT_PROXIED_AS', '').rstrip('/')
    if root:
        return f'{root}{path}'
    service_url = request.build_absolute_uri(path)
    if getattr(settings, 'CAS_FORCE_SSL_SERVICE_URL', False):
        service_url = service_url.replace('http://', 'https://', 1)
    return service_url


def logout_view(request):
    """Logout view — redirect to SSO if CAS is enabled"""
    cas_enabled = getattr(settings, 'CAS_ENABLED', False)
    cas_server = getattr(settings, 'CAS_SERVER_URL', '')

    auth_logout(request)

    if cas_enabled and cas_server:
        # Μετά το SSO logout, ο χρήστης επιστρέφει απευθείας στη σελίδα σύνδεσης
        service_url = _cas_service_url(request, reverse('accounts:login'))
        cas_server_clean = cas_server.rstrip('/')
        return redirect(f'{cas_server_clean}/logout?service={quote(service_url, safe="")}')

    messages.info(request, 'Αποσυνδεθήκατε επιτυχώς.')
    return redirect('accounts:login')


def register_view(request):
    """Εγγραφή νέων χρηστών"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)

        if form.is_valid():
            try:
                user = form.save()
                import logging
                logger = logging.getLogger(__name__)
                logger.info(f"New user registered: {user.email}")
                messages.success(request,
                    f'Η εγγραφή σας ολοκληρώθηκε επιτυχώς! '
                    f'Η αίτησή σας στάλθηκε για έγκριση. '
                    f'Θα ενημερωθείτε όταν εγκριθεί η πρόσβασή σας στο σύστημα.')
                return redirect('accounts:registration_pending')
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error saving user during registration: {e}")
                messages.error(request, f'Σφάλμα κατά την εγγραφή: {e}')
        else:
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