from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.http import JsonResponse
from django.contrib import messages
from .models import Notification
from .utils import mark_all_notifications_as_read


class NotificationListView(LoginRequiredMixin, ListView):
    """Λίστα ειδοποιήσεων χρήστη"""
    model = Notification
    template_name = 'notifications/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Στατιστικά
        context.update({
            'total_notifications': self.get_queryset().count(),
            'unread_count': self.get_queryset().filter(is_read=False).count(),
            'read_count': self.get_queryset().filter(is_read=True).count(),
        })
        
        return context


@login_required
def mark_notification_as_read(request, pk):
    """Σήμανση συγκεκριμένης ειδοποίησης ως διαβασμένη"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    notification.mark_as_read()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    
    return redirect('notifications:notification_list')


@login_required
def mark_all_as_read(request):
    """Σήμανση όλων των ειδοποιήσεων ως διαβασμένες"""
    count = mark_all_notifications_as_read(request.user)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'count': count})
    
    if count > 0:
        messages.success(request, f'{count} ειδοποιήσεις σημάνθηκαν ως διαβασμένες.')
    else:
        messages.info(request, 'Δεν υπήρχαν μη διαβασμένες ειδοποιήσεις.')
    
    return redirect('notifications:notification_list')


@login_required
def delete_notification(request, pk):
    """Διαγραφή συγκεκριμένης ειδοποίησης"""
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    
    if request.method == 'POST':
        notification.delete()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
        messages.success(request, 'Η ειδοποίηση διαγράφηκε επιτυχώς.')
    
    return redirect('notifications:notification_list')


@login_required
def get_unread_count(request):
    """API endpoint για τον αριθμό μη διαβασμένων ειδοποιήσεων"""
    unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'unread_count': unread_count})


@login_required
def get_recent_notifications(request):
    """API endpoint για τις πρόσφατες ειδοποιήσεις (για dropdown)"""
    notifications = Notification.objects.filter(
        user=request.user
    ).select_related('content_type')[:10]
    
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': notification.id,
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'is_read': notification.is_read,
            'created_at': notification.created_at.strftime('%d/%m/%Y %H:%M'),
            'badge_class': notification.type_badge_class,
        })
    
    return JsonResponse({
        'notifications': notifications_data,
        'unread_count': Notification.objects.filter(user=request.user, is_read=False).count()
    })