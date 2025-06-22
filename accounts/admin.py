from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department, Role


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


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'last_name', 'first_name', 'email', 'department', 'get_role_names', 'is_active')
    list_filter = ('roles', 'department', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'employee_id')
    ordering = ('last_name', 'first_name')
    filter_horizontal = ('roles',)  # Για καλύτερη διαχείριση ManyToMany
    
    def get_role_names(self, obj):
        """Επιστρέφει τα ονόματα των ρόλων για εμφάνιση στο admin"""
        return obj.get_role_names()
    get_role_names.short_description = 'Ρόλοι'
    
    fieldsets = UserAdmin.fieldsets + (
        ('Προσωπικά Στοιχεία', {
            'fields': ('phone', 'employee_id', 'hire_date')
        }),
        ('Υπηρεσιακά Στοιχεία', {
            'fields': ('department', 'roles')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Πρόσθετες Πληροφορίες', {
            'fields': ('first_name', 'last_name', 'email', 'department', 'roles')
        }),
    )