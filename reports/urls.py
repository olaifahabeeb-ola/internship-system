from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('',                              views.reports_index,         name='index'),
    path('student/<int:student_id>/',      views.student_report,        name='student_report'),
    path('student/<int:student_id>/pdf/',  views.student_report_pdf,    name='student_report_pdf'),
    path('student/<int:student_id>/csv/',  views.student_report_csv,    name='student_report_csv'),
    path('aggregate/',                     views.aggregate_report,      name='aggregate'),
    path('aggregate/pdf/',                 views.aggregate_report_pdf,  name='aggregate_pdf'),
    path('aggregate/csv/',                 views.aggregate_report_csv,  name='aggregate_csv'),
]
