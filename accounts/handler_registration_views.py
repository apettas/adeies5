"""Views για διαχείριση εκκρεμών εγγραφών χρηστών από χειριστή αδειών."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from accounts.forms import HandlerUserActivationForm
from accounts.models import PendingRegistrationAcknowledgment, User
from accounts.utils.pending_registration_alerts import (
    get_pending_registration_alerts,
    get_pending_registrations_queryset,
)


class LeaveHandlerRequiredMixin(LoginRequiredMixin):
    """Πρόσβαση μόνο για χειριστές αδειών."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_leave_handler:
            raise PermissionDenied('Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.')
        return super().dispatch(request, *args, **kwargs)


class PendingUserRegistrationsListView(LeaveHandlerRequiredMixin, ListView):
    """Λίστα εκκρεμών εγγραφών χρηστών."""

    model = User
    template_name = 'accounts/pending_user_registrations_list.html'
    context_object_name = 'pending_users'
    paginate_by = 20

    def get_queryset(self):
        return get_pending_registrations_queryset()


class PendingUserRegistrationReviewView(LeaveHandlerRequiredMixin, DetailView):
    """Έλεγχος στοιχείων και ενεργοποίηση εκκρεμούς εγγραφής."""

    model = User
    template_name = 'accounts/pending_user_registration_review.html'
    context_object_name = 'pending_user'
    pk_url_kwarg = 'user_id'

    def get_queryset(self):
        return get_pending_registrations_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.method == 'POST':
            context['form'] = HandlerUserActivationForm(
                self.request.POST,
                instance=self.object,
            )
        else:
            context['form'] = HandlerUserActivationForm(instance=self.object)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = HandlerUserActivationForm(request.POST, instance=self.object)
        action = request.POST.get('action', 'save')

        if not form.is_valid():
            messages.error(request, 'Παρακαλώ διορθώστε τα σφάλματα στη φόρμα.')
            return self.render_to_response(self.get_context_data(form=form))

        user = form.save(commit=False)
        user.approval_notes = form.cleaned_data.get('approval_notes', '')
        user.save()
        form.save_m2m()

        if action == 'activate':
            if not user.employee_type_id:
                messages.error(request, 'Η κατηγορία υπαλλήλου είναι υποχρεωτική για ενεργοποίηση.')
                return redirect('leaves:pending_user_registration_review', user_id=user.pk)
            if not user.roles.exists():
                messages.error(request, 'Πρέπει να οριστεί τουλάχιστον ένας ρόλος.')
                return redirect('leaves:pending_user_registration_review', user_id=user.pk)

            user.approve_registration(request.user, user.approval_notes)
            messages.success(
                request,
                f'Ο χρήστης {user.get_full_name()} ενεργοποιήθηκε επιτυχώς. '
                f'Στάλθηκε email ειδοποίησης στο {user.email}.',
            )
            return redirect('leaves:pending_user_registrations')

        messages.success(request, 'Τα στοιχεία αποθηκεύτηκαν.')
        return redirect('leaves:pending_user_registration_review', user_id=user.pk)


@login_required
def acknowledge_pending_registration(request, user_id):
    """Δήλωση γνώσης για νέα εγγραφή χρήστη."""
    if not request.user.is_leave_handler:
        raise PermissionDenied('Δεν έχετε δικαίωμα.')

    pending_user = get_object_or_404(
        get_pending_registrations_queryset(),
        pk=user_id,
    )
    PendingRegistrationAcknowledgment.objects.get_or_create(
        handler=request.user,
        pending_user=pending_user,
    )
    messages.success(request, 'Η γνώση καταχωρήθηκε.')
    return redirect('leaves:handler_dashboard')


@login_required
@require_POST
def reject_pending_registration(request, user_id):
    """Οριστική διαγραφή άσχετης/λανθασμένης εκκρεμούς εγγραφής."""
    if not request.user.is_leave_handler:
        raise PermissionDenied('Δεν έχετε δικαίωμα.')

    pending_user = get_object_or_404(
        get_pending_registrations_queryset(),
        pk=user_id,
    )
    full_name = pending_user.get_full_name()
    email = pending_user.email
    pending_user.delete()
    messages.success(
        request,
        f'Η εγγραφή του χρήστη {full_name} ({email}) διαγράφηκε οριστικά.',
    )
    return redirect('leaves:pending_user_registrations')
