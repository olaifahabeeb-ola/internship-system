from django.contrib import admin
from .models import AssessmentCriteria, Assessment, AssessmentScore, AssessmentSummary


@admin.register(AssessmentCriteria)
class AssessmentCriteriaAdmin(admin.ModelAdmin):
    list_display  = ('name', 'category', 'max_score', 'order', 'is_active')
    list_filter   = ('category', 'is_active')
    ordering      = ('order',)


class AssessmentScoreInline(admin.TabularInline):
    model  = AssessmentScore
    extra  = 0
    fields = ('criterion', 'score', 'comment')


class AssessmentSummaryInline(admin.StackedInline):
    model  = AssessmentSummary
    extra  = 0


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display  = ('student_name', 'assessment_type', 'status',
                     'total_score', 'percentage_display', 'supervisor', 'submission_date')
    list_filter   = ('assessment_type', 'status')
    search_fields = (
        'application__student__first_name',
        'application__student__last_name',
        'application__student__username',
    )
    readonly_fields = ('total_score', 'max_possible', 'submission_date', 'last_modified')
    inlines         = [AssessmentScoreInline, AssessmentSummaryInline]

    def student_name(self, obj):
        return obj.student.get_full_name()
    student_name.short_description = 'Student'

    def percentage_display(self, obj):
        return f"{obj.percentage}%"
    percentage_display.short_description = 'Score %'


@admin.register(AssessmentScore)
class AssessmentScoreAdmin(admin.ModelAdmin):
    list_display  = ('assessment', 'criterion', 'score')
    list_filter   = ('criterion',)


@admin.register(AssessmentSummary)
class AssessmentSummaryAdmin(admin.ModelAdmin):
    list_display  = ('assessment', 'recommendation', 'student_acknowledged',
                     'student_acknowledged_at')
    list_filter   = ('recommendation', 'student_acknowledged')
