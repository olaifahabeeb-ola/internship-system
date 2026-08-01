from django.contrib import admin
from .models import Announcement

@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display  = ('title', 'priority', 'target_audience', 'posted_by',
                     'is_active', 'created_at')
    list_filter   = ('priority', 'target_audience', 'is_active')
    search_fields = ('title', 'message')
    readonly_fields = ('created_at', 'updated_at')
