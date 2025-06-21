from django.contrib import admin
from .models import LeaveType, LeaveRequest, LeaveRequestDocument


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'max_days_per_year', 'requires_documents', 'logic_handler', 'is_active')
    list_filter = ('requires_documents', 'logic_handler', 'is_active')
    search_fields = ('name', 'code')
    ordering = ('name',)


class LeaveRequestDocumentInline(admin.TabularInline):
    model = LeaveRequestDocument
    extra = 0
    readonly_fields = ('uploaded_at', 'uploaded_by')


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ('employee', 'leave_type', 'start_date', 'end_date', 'total_days', 'status', 'created_at')
    list_filter = ('status', 'leave_type', 'created_at', 'start_date')
    search_fields = ('employee__first_name', 'employee__last_name', 'employee__username', 'protocol_number')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Βασικά Στοιχεία', {
            'fields': ('employee', 'leave_type', 'start_date', 'end_date', 'total_days', 'description')
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
        ('Απόρριψη', {
            'fields': ('rejected_by', 'rejected_at', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        ('Χρονικές Σφραγίδες', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('total_days', 'created_at', 'updated_at')
    inlines = [LeaveRequestDocumentInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'employee', 'leave_type', 'manager_approved_by', 'processed_by', 'rejected_by'
        )


@admin.register(LeaveRequestDocument)
class LeaveRequestDocumentAdmin(admin.ModelAdmin):
    list_display = ('leave_request', 'description', 'uploaded_by', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('leave_request__employee__first_name', 'leave_request__employee__last_name', 'description')
    ordering = ('-uploaded_at',)
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('leave_request', 'uploaded_by')