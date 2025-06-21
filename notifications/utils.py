from django.contrib.contenttypes.models import ContentType
from .models import Notification


def create_notification(user, title, message, notification_type='info', related_object=None):
    """
    Δημιουργία νέας ειδοποίησης
    
    Args:
        user: Ο χρήστης που θα λάβει την ειδοποίηση
        title: Ο τίτλος της ειδοποίησης
        message: Το μήνυμα της ειδοποίησης
        notification_type: Ο τύπος ('info', 'success', 'warning', 'error')
        related_object: Προαιρετικό αντικείμενο που σχετίζεται με την ειδοποίηση
    
    Returns:
        Notification instance
    """
    
    notification_data = {
        'user': user,
        'title': title,
        'message': message,
        'notification_type': notification_type,
    }
    
    # Αν υπάρχει σχετιζόμενο αντικείμενο, προσθέτουμε το Generic Foreign Key
    if related_object:
        notification_data['content_type'] = ContentType.objects.get_for_model(related_object)
        notification_data['object_id'] = related_object.pk
    
    notification = Notification.objects.create(**notification_data)
    return notification


def get_unread_notifications_count(user):
    """
    Επιστρέφει τον αριθμό των μη διαβασμένων ειδοποιήσεων για έναν χρήστη
    """
    return Notification.objects.filter(user=user, is_read=False).count()


def mark_all_notifications_as_read(user):
    """
    Σημαίνει όλες τις ειδοποιήσεις ενός χρήστη ως διαβασμένες
    """
    from django.utils import timezone
    
    unread_notifications = Notification.objects.filter(user=user, is_read=False)
    unread_notifications.update(is_read=True, read_at=timezone.now())
    
    return unread_notifications.count()


def delete_old_notifications(days_old=30):
    """
    Διαγραφή παλιών ειδοποιήσεων που είναι παλαιότερες από τον καθορισμένο αριθμό ημερών
    """
    from django.utils import timezone
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days_old)
    old_notifications = Notification.objects.filter(created_at__lt=cutoff_date)
    count = old_notifications.count()
    old_notifications.delete()
    
    return count