from django.urls import path
from . import views

app_name = 'logbook'

urlpatterns = [

    # ── Student ───────────────────────────────────────────────────
    path('submit/',                         views.submit_log,           name='submit_entry'),
    path('my-logs/',                        views.my_logbook,            name='my_logbook'),
    path('my-logs/<int:pk>/',               views.log_detail,            name='log_detail'),
    path('my-logs/<int:pk>/edit/',          views.edit_log,              name='edit_log'),
    path('my-logs/<int:pk>/delete/',        views.delete_log,            name='delete_log'),
    path('weekly-report/',                  views.submit_weekly_report,  name='submit_weekly_report'),
    path('my-weekly-reports/',              views.my_weekly_reports,     name='my_weekly_reports'),

    # ── Supervisor ────────────────────────────────────────────────
    path('review/',                         views.review_list,               name='review_list'),
    path('review/<int:pk>/',                views.review_detail,             name='review_detail'),
    path('review/<int:pk>/full/',           views.supervisor_review_log,     name='supervisor_review_log'),
    path('review/bulk-approve/',            views.bulk_approve,              name='bulk_approve'),
    path('my-students/',                    views.supervisor_student_list,   name='supervisor_student_list'),
    path('student/<int:app_pk>/logs/',      views.supervisor_student_logbook,name='supervisor_student_logbook'),
    path('student/<int:app_pk>/reports/',   views.supervisor_weekly_reports, name='supervisor_weekly_reports'),

    # ── Coordinator ───────────────────────────────────────────────
    path('monitor/',                        views.coordinator_monitor,       name='coordinator_overview'),
    path('monitor/student/<int:app_pk>/',   views.coordinator_student_logbook,name='coordinator_student_logbook'),

    # Shared alias used by coordinator dashboard links
    path('student/<int:app_pk>/',           views.student_logbook,           name='student_logbook'),
]