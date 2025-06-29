from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone
from .models import User, Department, Role, Specialty, Headquarters, Prefecture


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('name',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department_type', 'parent_department', 'headquarters', 'prefecture', 'is_active')
    list_filter = ('department_type', 'is_active', 'headquarters', 'prefecture')
    search_fields = ('name', 'code')
    ordering = ('name',)

@admin.register(Headquarters)
class HeadquartersAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code')
    ordering = ('name',)
    readonly_fields = ('created_at',)

@admin.register(Prefecture)
class PrefectureAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code')
    ordering = ('name',)
    readonly_fields = ('created_at',)


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('specialties_short', 'specialties_full', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('specialties_full', 'specialties_short')
    ordering = ('specialties_short', 'specialties_full')
    readonly_fields = ('created_at',)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'last_name', 'first_name', 'department', 'specialty', 'get_role_names', 'get_category_display', 'get_registration_status_display', 'is_active')
    list_filter = ('roles', 'department', 'specialty', 'user_category', 'registration_status', 'is_active', 'is_staff')
    search_fields = ('first_name', 'last_name', 'email', 'employee_id')
    ordering = ('last_name', 'first_name')
    filter_horizontal = ('roles',)
    actions = ['approve_users', 'reject_users']
    
    def get_role_names(self, obj):
        """Επιστρέφει τα ονόματα των ρόλων για εμφάνιση στο admin"""
        return obj.get_role_names()
    get_role_names.short_description = 'Ρόλοι'
    
    def get_category_display(self, obj):
        """Επιστρέφει την ελληνική ονομασία της κατηγορίας χρήστη"""
        return obj.get_user_category_display()
    get_category_display.short_description = 'Κατηγορία'
    
    def get_registration_status_display(self, obj):
        """Επιστρέφει την κατάσταση εγγραφής με χρωματισμό"""
        status = obj.get_registration_status_display()
        if obj.registration_status == 'PENDING':
            return format_html('<span style="color: orange;">⏳ {}</span>', status)
        elif obj.registration_status == 'APPROVED':
            return format_html('<span style="color: green;">✅ {}</span>', status)
        elif obj.registration_status == 'REJECTED':
            return format_html('<span style="color: red;">❌ {}</span>', status)
        return status
    get_registration_status_display.short_description = 'Κατάσταση Εγγραφής'
    
    def approve_users(self, request, queryset):
        """Action για έγκριση χρηστών"""
        approved_count = 0
        for user in queryset.filter(registration_status='PENDING'):
            user.approve_registration(request.user, 'Έγκριση μέσω admin interface')
            approved_count += 1
        
        if approved_count == 1:
            message = f'Εγκρίθηκε 1 χρήστης.'
        else:
            message = f'Εγκρίθηκαν {approved_count} χρήστες.'
        self.message_user(request, message)
    approve_users.short_description = 'Έγκριση επιλεγμένων χρηστών'
    
    def reject_users(self, request, queryset):
        """Action για απόρριψη χρηστών"""
        rejected_count = 0
        for user in queryset.filter(registration_status='PENDING'):
            user.reject_registration(request.user, 'Απόρριψη μέσω admin interface')
            rejected_count += 1
            
        if rejected_count == 1:
            message = f'Απορρίφθηκε 1 χρήστης.'
        else:
            message = f'Απορρίφθηκαν {rejected_count} χρήστες.'
        self.message_user(request, message)
    reject_users.short_description = 'Απόρριψη επιλεγμένων χρηστών'
    
    # Προσαρμογή fieldsets για email-based authentication (χωρίς username)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Προσωπικά Στοιχεία', {'fields': ('first_name', 'last_name', 'phone', 'employee_id', 'hire_date')}),
        ('Υπηρεσιακά Στοιχεία', {'fields': ('department', 'specialty', 'roles', 'user_category')}),
        ('Κατάσταση Εγγραφής', {'fields': ('registration_status', 'registration_date', 'approved_by', 'approval_date', 'approval_notes')}),
        ('Δικαιώματα', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Σημαντικές Ημερομηνίες', {'fields': ('last_login', 'date_joined')}),
    )
    
    readonly_fields = ('registration_date', 'approval_date')
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2'),
        }),
        ('Προσωπικά Στοιχεία', {
            'classes': ('wide',),
            'fields': ('first_name', 'last_name', 'phone', 'employee_id', 'hire_date')
        }),
        ('Υπηρεσιακά Στοιχεία', {
            'classes': ('wide',),
            'fields': ('department', 'specialty', 'roles', 'user_category')
        }),
    )
