from django.contrib import admin
from .models import (
    LeaveType, LeaveRequest, LeavePeriod, SecureFile,
    Logo, Info, Ypopsin, Signee,
    PublicHoliday, LeaveActionLog, LeaveAccessLog, RegularLeaveBalanceEntry,
    YCCommitteeAcknowledgment,
    DocumentUploadAcknowledgment,
    YearlySickLeaveTotal
)


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'max_days', 'requires_approval', 'workflow_variant', 'is_revocation', 'is_active', 'has_instructions')
    list_filter = ('is_active', 'requires_approval', 'is_revocation', 'workflow_variant', 'is_sick_leave_yd', 'is_sick_leave_total')
    search_fields = ('name', 'code', 'subject_text', 'decision_text')
    readonly_fields = ('id', 'created_at')
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('id', 'code', 'name', 'max_days', 'requires_approval', 'is_simple', 'is_active')
        }),
        ('Κείμενα & Οδηγίες', {
            'fields': ('subject_text', 'decision_text', 'instructions')
        }),
        ('Ταξινόμηση', {
            'fields': ('workflow_variant',)
        }),
        ('Υπόλοιπο', {
            'fields': ('affects_regular_leave_balance',)
        }),
        ('Ειδικές Κατηγορίες', {
            'fields': ('is_sick_leave_yd', 'is_sick_leave_total', 'is_revocation')
        }),
        ('Χρονοσήμανση', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'leave_type', 'days', 'status', 'submitted_at', 'kedasy_kepea_protocol_number', 'pdede_protocol_number', 'protocol_number')
    list_filter = ('status', 'leave_type', 'created_at', 'locking_user')
    search_fields = ('user__first_name', 'user__last_name', 'user__email', 'protocol_number', 'kedasy_kepea_protocol_number', 'pdede_protocol_number')
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('user', 'leave_type', 'description', 'requested_days', 'days', 'status')
        }),
        ('Πρωτόκολλο ΚΕΔΑΣΥ/ΚΕΠΕΑ', {
            'fields': ('kedasy_kepea_protocol_number', 'kedasy_kepea_protocol_date', 'kedasy_kepea_protocol_by')
        }),
        ('Πρωτόκολλο ΠΔΕΔΕ', {
            'fields': ('pdede_protocol_number', 'pdede_protocol_date', 'pdede_protocol_details', 'pdede_protocol_by')
        }),
        ('Πρωτόκολλο ΣΗΔΕ', {
            'fields': ('protocol_number', 'protocol_pdf_path', 'protocol_pdf_size', 'protocol_created_at')
        }),
        ('Κατάσταση & Έγκριση', {
            'fields': ('submitted_at', 'manager_approved_by', 'manager_approved_at', 'manager_comments')
        }),
        ('Επεξεργασία', {
            'fields': ('processed_by', 'processed_at', 'processing_comments')
        }),
        ('Απόφαση', {
            'fields': ('final_decision_text', 'decision_logo', 'decision_info', 'decision_ypopsin', 'decision_signee')
        }),
        ('PDF Απόφασης', {
            'fields': ('decision_pdf_path', 'decision_pdf_size', 'decision_created_at')
        }),
        ('Ακριβές Αντίγραφο ΣΗΔΕ', {
            'fields': ('exact_copy_pdf_path', 'exact_copy_pdf_size', 'exact_copy_uploaded_by', 'exact_copy_uploaded_at')
        }),
        ('Συγχωνευμένο PDF', {
            'fields': ('merged_pdf_path', 'merged_pdf_size', 'merged_pdf_created_at', 'merged_pdf_sent_at')
        }),
        ('Δικαιολογητικά', {
            'fields': ('required_documents', 'documents_deadline', 'documents_requested_by', 'documents_requested_at', 'documents_provided_by', 'documents_provided_at', 'documents_notes')
        }),
        ('Απόρριψη', {
            'fields': ('rejected_by', 'rejected_at', 'rejection_reason')
        }),
        ('Επιστροφή', {
            'fields': ('return_notes', 'returned_by', 'returned_at')
        }),
        ('Ανάκληση / Διαγραφή', {
            'fields': ('parent_leave', 'revoked_days')
        }),
        ('Κλείδωμα', {
            'fields': ('locking_user', 'locked_at')
        }),
        ('Ολοκλήρωση', {
            'fields': ('completed_at',)
        }),
    )
    readonly_fields = ('created_at', 'updated_at', 'submitted_at', 'manager_approved_at', 'manager_approved_by', 'processed_at', 'rejected_at', 'completed_at', 'protocol_created_at', 'decision_created_at', 'merged_pdf_created_at', 'merged_pdf_sent_at', 'exact_copy_uploaded_at', 'documents_requested_at', 'documents_provided_at', 'locked_at', 'returned_at')
    # Remove flawed 'periods' field display since it's not a direct FK field

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


@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'year', 'is_movable', 'is_active')
    list_filter = ('is_active', 'is_movable', 'year')
    search_fields = ('name',)
    date_hierarchy = 'date'


@admin.register(LeaveActionLog)
class LeaveActionLogAdmin(admin.ModelAdmin):
    list_display = ('leave_request', 'action', 'user', 'previous_status', 'new_status', 'timestamp')
    list_filter = ('action', 'previous_status', 'new_status', 'timestamp')
    search_fields = ('leave_request__user__first_name', 'leave_request__user__last_name', 'notes')
    readonly_fields = ('leave_request', 'user', 'action', 'previous_status', 'new_status',
                       'timestamp', 'notes', 'ip_address')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(LeaveAccessLog)
class LeaveAccessLogAdmin(admin.ModelAdmin):
    list_display = ('leave_request', 'accessed_by', 'access_type', 'timestamp', 'ip_address')
    list_filter = ('access_type', 'timestamp')
    search_fields = ('leave_request__user__first_name', 'leave_request__user__last_name', 'accessed_by__email')
    readonly_fields = ('leave_request', 'accessed_by', 'access_type', 'timestamp', 'ip_address')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(RegularLeaveBalanceEntry)
class RegularLeaveBalanceEntryAdmin(admin.ModelAdmin):
    list_display = ('employee', 'entry_type', 'entry_date', 'days_delta', 'balance_after', 'leave_request', 'created_by')
    list_filter = ('entry_type', 'entry_date', 'is_locked')
    search_fields = ('employee__email', 'employee__first_name', 'employee__last_name', 'description', 'notes')
    readonly_fields = ('created_at', 'created_by', 'is_locked')


@admin.register(YearlySickLeaveTotal)
class YearlySickLeaveTotalAdmin(admin.ModelAdmin):
    list_display = ('employee', 'year', 'total_days', 'is_locked', 'created_at')
    list_filter = ('year', 'is_locked')
    search_fields = ('employee__email', 'employee__last_name', 'employee__first_name', 'notes')
    list_editable = ('total_days',)
    ordering = ('-year', 'employee__last_name', 'employee__first_name')


@admin.register(YCCommitteeAcknowledgment)
class YCCommitteeAcknowledgmentAdmin(admin.ModelAdmin):
    list_display = ('handler', 'employee', 'acknowledged_at')
    list_filter = ('acknowledged_at',)
    search_fields = ('handler__email', 'handler__last_name', 'employee__email', 'employee__last_name')
    readonly_fields = ('acknowledged_at',)


@admin.register(DocumentUploadAcknowledgment)
class DocumentUploadAcknowledgmentAdmin(admin.ModelAdmin):
    list_display = ('handler', 'leave_request', 'acknowledged_at')
    list_filter = ('acknowledged_at',)
    search_fields = ('handler__email', 'leave_request__id')
    readonly_fields = ('acknowledged_at',)
