from django.contrib import admin
from .models import LeaveType, LeaveRequest, LeavePeriod, SecureFile


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_days', 'requires_approval', 'is_active')
    list_filter = ('requires_approval', 'is_active')
    search_fields = ('name', 'description')
    ordering = ('name',)


class LeavePeriodInline(admin.TabularInline):
    model = LeavePeriod
    extra = 1
    fields = ('start_date', 'end_date')
    readonly_fields = ('created_at',)


class SecureFileInline(admin.TabularInline):
    model = SecureFile
    extra = 0
    readonly_fields = ('uploaded_at', 'uploaded_by', 'file_size', 'content_type')
    fields = ('original_filename', 'file_size', 'content_type', 'uploaded_by', 'uploaded_at')
    
    def has_add_permission(self, request, obj):
        # Απενεργοποίηση προσθήκης αρχείων από το admin για ασφάλεια
        return False


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'leave_type', 'start_date', 'end_date', 'total_days', 'status', 'created_at')
    list_filter = ('status', 'leave_type', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'protocol_number')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('user', 'leave_type', 'description')
        }),
        ('Κατάσταση', {
            'fields': ('status', 'protocol_number')
        }),
        ('Έγκριση Προϊσταμένου', {
            'fields': ('manager_approved_by', 'manager_approved_at', 'manager_comments'),
            'classes': ('collapse',)
        }),
        ('Επεξεργασία', {
            'fields': ('processed_by', 'processed_at', 'processing_comments'),
            'classes': ('collapse',)
        }),
        ('Ολοκλήρωση', {
            'fields': ('completed_at',),
            'classes': ('collapse',)
        }),
        ('Απόρριψη', {
            'fields': ('rejected_by', 'rejected_at', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        ('Χρονικές Σφραγίδες', {
            'fields': ('created_at', 'updated_at', 'submitted_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('total_days', 'start_date', 'end_date', 'created_at', 'updated_at')
    inlines = [LeavePeriodInline, SecureFileInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'leave_type', 'manager_approved_by', 'processed_by', 'rejected_by'
        )
    
    def total_days(self, obj):
        return obj.total_days
    total_days.short_description = 'Συνολικές Ημέρες'
    
    def start_date(self, obj):
        return obj.start_date
    start_date.short_description = 'Ημερομηνία Έναρξης'
    
    def end_date(self, obj):
        return obj.end_date
    end_date.short_description = 'Ημερομηνία Λήξης'


@admin.register(LeavePeriod)
class LeavePeriodAdmin(admin.ModelAdmin):
    list_display = ('leave_request', 'start_date', 'end_date', 'days', 'created_at')
    list_filter = ('start_date', 'end_date', 'created_at')
    search_fields = ('leave_request__user__first_name', 'leave_request__user__last_name')
    ordering = ('-created_at',)
    date_hierarchy = 'start_date'
    
    def days(self, obj):
        return (obj.end_date - obj.start_date).days + 1
    days.short_description = 'Ημέρες'


@admin.register(SecureFile)
class SecureFileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'leave_request', 'uploaded_by', 'file_size_display', 'uploaded_at')
    list_filter = ('uploaded_at', 'content_type')
    search_fields = ('original_filename', 'leave_request__user__first_name', 'leave_request__user__last_name')
    ordering = ('-uploaded_at',)
    readonly_fields = ('file_path', 'encryption_key', 'file_size', 'content_type', 'uploaded_at')
    
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('leave_request', 'original_filename', 'uploaded_by')
        }),
        ('Τεχνικά Στοιχεία', {
            'fields': ('content_type', 'file_size', 'uploaded_at'),
            'classes': ('collapse',)
        }),
        ('Ασφάλεια (Μη Επεξεργάσιμα)', {
            'fields': ('file_path', 'encryption_key'),
            'classes': ('collapse',),
            'description': 'Αυτά τα πεδία δεν πρέπει να επεξεργάζονται για λόγους ασφαλείας.'
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('leave_request', 'uploaded_by')
    
    def file_size_display(self, obj):
        """Εμφάνιση μεγέθους αρχείου σε ανθρώπινα κατανοητή μορφή"""
        if obj.file_size < 1024:
            return f"{obj.file_size} bytes"
        elif obj.file_size < 1024 * 1024:
            return f"{obj.file_size / 1024:.1f} KB"
        else:
            return f"{obj.file_size / (1024 * 1024):.2f} MB"
    file_size_display.short_description = 'Μέγεθος Αρχείου'
    
    def has_add_permission(self, request):
        # Απενεργοποίηση προσθήκης αρχείων από το admin για ασφάλεια
        return False
    
    def has_change_permission(self, request, obj=None):
        # Περιορισμένη επεξεργασία για ασφάλεια
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        # Μόνο superusers μπορούν να διαγράψουν αρχεία από το admin
        return request.user.is_superuser