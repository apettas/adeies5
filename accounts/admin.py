from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department, Role, Specialty


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    ordering = ('name',)


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department_type', 'parent_department', 'is_active')
    list_filter = ('department_type', 'is_active')
    search_fields = ('name', 'code')
    ordering = ('name',)


@admin.register(Specialty)
class SpecialtyAdmin(admin.ModelAdmin):
    list_display = ('specialties_short', 'specialties_full', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('specialties_full', 'specialties_short')
    ordering = ('specialties_short', 'specialties_full')
    readonly_fields = ('created_at',)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'last_name', 'first_name', 'department', 'specialty', 'get_role_names', 'get_category_display', 'is_active')
    list_filter = ('roles', 'department', 'specialty', 'user_category', 'is_active', 'is_staff')
    search_fields = ('first_name', 'last_name', 'email', 'employee_id')
    ordering = ('last_name', 'first_name')
    filter_horizontal = ('roles',)
    
    def get_role_names(self, obj):
        """Επιστρέφει τα ονόματα των ρόλων για εμφάνιση στο admin"""
        return obj.get_role_names()
    get_role_names.short_description = 'Ρόλοι'
    
    def get_category_display(self, obj):
        """Επιστρέφει την ελληνική ονομασία της κατηγορίας χρήστη"""
        return obj.get_user_category_display()
    get_category_display.short_description = 'Κατηγορία'
    
    # Προσαρμογή fieldsets για email-based authentication (χωρίς username)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Προσωπικά Στοιχεία', {'fields': ('first_name', 'last_name', 'phone', 'employee_id', 'hire_date')}),
        ('Υπηρεσιακά Στοιχεία', {'fields': ('department', 'specialty', 'roles', 'user_category')}),
        ('Δικαιώματα', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Σημαντικές Ημερομηνίες', {'fields': ('last_login', 'date_joined')}),
    )
    
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