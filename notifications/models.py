from django.db import models
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

User = get_user_model()


class Notification(models.Model):
    """Μοντέλο ειδοποιήσεων"""
    
    NOTIFICATION_TYPES = [
        ('info', 'Πληροφορία'),
        ('success', 'Επιτυχία'),
        ('warning', 'Προειδοποίηση'),
        ('error', 'Σφάλμα'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, 
                           verbose_name='Χρήστης', related_name='notifications')
    title = models.CharField('Τίτλος', max_length=200)
    message = models.TextField('Μήνυμα')
    notification_type = models.CharField('Τύπος', max_length=10, choices=NOTIFICATION_TYPES, default='info')
    
    # Generic Foreign Key για σύνδεση με οποιοδήποτε άλλο μοντέλο
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Κατάσταση ειδοποίησης
    is_read = models.BooleanField('Αναγνώστηκε', default=False)
    read_at = models.DateTimeField('Ημερομηνία Ανάγνωσης', null=True, blank=True)
    
    # Χρονικές σφραγίδες
    created_at = models.DateTimeField('Ημερομηνία Δημιουργίας', auto_now_add=True)
    
    class Meta:
        verbose_name = 'Ειδοποίηση'
        verbose_name_plural = 'Ειδοποιήσεις'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.full_name} - {self.title}"
    
    def mark_as_read(self):
        """Σήμανση ως αναγνωσμένη"""
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    @property
    def type_badge_class(self):
        """CSS class για το badge ανάλογα με τον τύπο"""
        type_classes = {
            'info': 'badge-info',
            'success': 'badge-success',
            'warning': 'badge-warning',
            'error': 'badge-danger',
        }
        return type_classes.get(self.notification_type, 'badge-secondary')