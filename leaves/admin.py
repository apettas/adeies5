from django.contrib import admin
from .models import LeaveType, LeaveRequest, LeavePeriod, SecureFile, Logo, Info, Ypopsin, Signee


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'max_days', 'requires_approval', 'is_active', 'general_category')
    list_filter = ('is_active', 'requires_approval', 'general_category')
    search_fields = ('name', 'description', 'subject_text', 'decision_text', 'folder', 'general_category')
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('name', 'description', 'max_days', 'requires_approval', 'is_active')
        }),
        ('Πρόσθετα Στοιχεία', {
            'fields': ('subject_text', 'decision_text', 'folder', 'general_category')
        }),
    )


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'leave_type', 'start_date', 'end_date', 'total_days', 'status', 'created_at')
    list_filter = ('status', 'leave_type', 'created_at')
    search_fields = ('user__first_name', 'user__last_name', 'user__username', 'protocol_number')
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('user', 'leave_type', 'description')
        }),
        ('Διαστήματα', {
            'fields': ('periods',)
        }),
        ('Κατάσταση', {
            'fields': ('status', 'submitted_at', 'manager_approved_by', 'manager_approved_at', 'manager_comments')
        }),
        ('Επεξεργασία', {
            'fields': ('protocol_number', 'processed_by', 'processed_at', 'processing_comments')
        }),
        ('Απόρριψη', {
            'fields': ('rejected_by', 'rejected_at', 'rejection_reason')
        }),
        ('Ολοκλήρωση', {
            'fields': ('completed_at',)
        }),
    )
    # Removed filter_horizontal as periods is not a many-to-many field
    readonly_fields = ('created_at', 'updated_at', 'submitted_at', 'manager_approved_at', 'processed_at', 'rejected_at', 'completed_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'leave_type', 'manager_approved_by', 'processed_by', 'rejected_by'
        )


@admin.register(LeavePeriod)
class LeavePeriodAdmin(admin.ModelAdmin):
    list_display = ('leave_request', 'start_date', 'end_date', 'days')
    list_filter = ('start_date', 'end_date')
    search_fields = ('leave_request__user__first_name', 'leave_request__user__last_name')


@admin.register(SecureFile)
class SecureFileAdmin(admin.ModelAdmin):
    list_display = ('original_filename', 'leave_request', 'uploaded_by', 'uploaded_at', 'file_size')
    list_filter = ('uploaded_at', 'content_type')
    search_fields = ('original_filename', 'leave_request__user__first_name', 'leave_request__user__last_name')
    readonly_fields = ('uploaded_at', 'file_size', 'content_type', 'encryption_key', 'file_path')


@admin.register(Logo)
class LogoAdmin(admin.ModelAdmin):
    list_display = ('logo_short', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('logo_short', 'logo')
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('logo_short', 'logo', 'is_active')
        }),
        ('Χρονοσήμανση', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Info)
class InfoAdmin(admin.ModelAdmin):
    list_display = ('info_short', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('info_short', 'info')
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('info_short', 'info', 'is_active')
        }),
        ('Χρονοσήμανση', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Ypopsin)
class YpopsinAdmin(admin.ModelAdmin):
    list_display = ('ypopsin_short', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('ypopsin_short', 'ypopsin')
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('ypopsin_short', 'ypopsin', 'is_active')
        }),
        ('Χρονοσήμανση', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Signee)
class SigneeAdmin(admin.ModelAdmin):
    list_display = ('signee_short', 'signee_name', 'is_active', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('signee_short', 'signee_name', 'signee')
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('signee_short', 'signee_name', 'signee', 'is_active')
        }),
        ('Χρονοσήμανση', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at')
