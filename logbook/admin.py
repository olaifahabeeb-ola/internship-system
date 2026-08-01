from django.contrib import admin
from .models import LogbookEntry, WeeklyReport


@admin.register(LogbookEntry)
class LogbookEntryAdmin(admin.ModelAdmin):
    list_display  = ('student_name', 'date', 'hours_worked',
                     'status', 'reviewed_by', 'created_at')
    list_filter   = ('status', 'date')
    search_fields = (
        'application__student__username',
        'application__student__first_name',
        'application__student__last_name',
        'activity_description',
    )
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at')
    ordering        = ('-date',)

    def student_name(self, obj):
        return obj.student.get_full_name()
    student_name.short_description = 'Student'


@admin.register(WeeklyReport)
class WeeklyReportAdmin(admin.ModelAdmin):
    list_display  = ('student_name', 'week_start', 'week_end',
                     'supervisor_approved', 'created_at')
    list_filter   = ('supervisor_approved',)
    search_fields = (
        'application__student__username',
        'application__student__first_name',
        'application__student__last_name',
    )
    readonly_fields = ('created_at',)

    def student_name(self, obj):
        return obj.student.get_full_name()
    student_name.short_description = 'Student'
