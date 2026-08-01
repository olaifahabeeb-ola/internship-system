from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """Extends the default UserAdmin to show our custom fields."""
    list_display  = (
        'username', 'email', 'first_name', 'last_name', 'role',
        'department', 'faculty', 'supervisor_department', 'is_active',
    )
    list_filter   = ('role', 'is_active', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name', 'matric_number')

    # Add our custom fields to the change form fieldsets
    fieldsets = UserAdmin.fieldsets + (
        ('Role & Profile', {
            'fields': ('role', 'phone',
                       'matric_number', 'department', 'programme', 'level', 'academic_session',
                       'company_name', 'company_address', 'job_title', 'supervisor_department',
                       'staff_id', 'faculty')
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role & Profile', {
            'fields': ('role', 'phone')
        }),
    )