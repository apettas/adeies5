from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'department_type', 'parent_department', 'is_active')
    list_filter = ('department_type', 'is_active')
    search_fields = ('name', 'code')
    ordering = ('name',)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'last_name', 'first_name', 'email', 'department', 'role', 'is_active')
    list_filter = ('role', 'department', 'is_active', 'is_staff')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'employee_id')
    ordering = ('last_name', 'first_name')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Προσωπικά Στοιχεία', {
            'fields': ('phone', 'employee_id', 'hire_date')
        }),
        ('Υπηρεσιακά Στοιχεία', {
            'fields': ('department', 'role', 'manager')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Πρόσθετες Πληροφορίες', {
            'fields': ('first_name', 'last_name', 'email', 'department', 'role', 'manager')
        }),
    )