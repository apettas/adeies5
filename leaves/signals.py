"""
Signals για αυτόματη καταγραφή audit trail
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from leaves.models import LeaveRequest, LeaveActionLog


@receiver(pre_save, sender=LeaveRequest)
def track_leave_status_changes(sender, instance, **kwargs):
    """
    Καταγράφει αλλαγές κατάστασης στο LeaveActionLog.
    Χρησιμοποιούμε pre_save για να πιάσουμε την προηγούμενη τιμή.
    """
    if not instance.pk:
        # Νέα αίτηση - θα καταγραφεί στο post_save
        return

    try:
        old_instance = LeaveRequest.objects.get(pk=instance.pk)
        old_status = old_instance.status
    except LeaveRequest.DoesNotExist:
        old_status = None

    # Αν άλλαξε το status, καταγράφουμε στο log
    if old_status != instance.status:
        # Αποθηκεύουμε την αλλαγή για χρήση στο post_save
        instance._status_changed = True
        instance._old_status = old_status
        instance._new_status = instance.status


@receiver(post_save, sender=LeaveRequest)
def create_status_change_log(sender, instance, created, **kwargs):
    """
    Δημιουργεί LeaveActionLog entry όταν αλλάζει status.
    """
    if created:
        # Νέα αίτηση
        LeaveActionLog.objects.create(
            leave_request=instance,
            user=instance.user,
            action='CREATE',
            previous_status='',
            new_status=instance.status,
            notes='Δημιουργία νέας αίτησης'
        )
        return

    # Έλεγχος για αλλαγή status
    if hasattr(instance, '_status_changed') and instance._status_changed:
        action_map = {
            'SUBMITTED': 'SUBMIT',
            'PENDING_PROTOCOL': 'MANAGER_APPROVE',
            'SUPERVISOR_REJECTED': 'MANAGER_REJECT',
            'PENDING_DOCUMENTS': 'REQUEST_DOCUMENTS',
            'IN_REVIEW': 'START_PROCESSING',
            'WAITING_FOR_DOCUMENTS': 'REQUEST_DOCUMENTS',
            'DECISION_PREPARATION': 'START_DECISION',
            'PENDING_SIGNATURES': 'SEND_TO_SIGNATURES',
            'COMPLETED': 'COMPLETE',
            'REJECTED_BY_LEAVES_DEPT': 'OPERATOR_REJECT',
            'CANCELLED_BY_APPLICANT': 'WITHDRAW',
        }

        action = action_map.get(instance._new_status, 'STATUS_CHANGE')

        # Βρίσκουμε τον χρήστη που έκανε την αλλαγή
        # (αυτό θα οριστεί από τα views μέσω middleware ή context)
        user = None
        if hasattr(instance, '_changed_by'):
            user = instance._changed_by
        elif hasattr(instance, 'processed_by') and instance.processed_by:
            user = instance.processed_by
        elif hasattr(instance, 'manager_approved_by') and instance.manager_approved_by:
            user = instance.manager_approved_by

        notes = ''
        if hasattr(instance, '_change_notes'):
            notes = instance._change_notes

        LeaveActionLog.objects.create(
            leave_request=instance,
            user=user,
            action=action,
            previous_status=instance._old_status,
            new_status=instance._new_status,
            notes=notes
        )

        # Καθαρισμός temporary attributes
        if hasattr(instance, '_status_changed'):
            del instance._status_changed
        if hasattr(instance, '_old_status'):
            del instance._old_status
        if hasattr(instance, '_new_status'):
            del instance._new_status
        if hasattr(instance, '_changed_by'):
            del instance._changed_by
        if hasattr(instance, '_change_notes'):
            del instance._change_notes
