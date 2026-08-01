from django.contrib import admin
from .models import Placement, Application


@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display  = ('title', 'company_name', 'location', 'slots_available',
                     'status', 'posted_by', 'created_at')
    list_filter   = ('status',)
    search_fields = ('title', 'company_name', 'location')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display  = ('student', 'placement', 'status', 'applied_at', 'reviewed_by')
    list_filter   = ('status',)
    search_fields = ('student__username', 'student__first_name', 'placement__title')
    readonly_fields = ('applied_at', 'reviewed_at')
