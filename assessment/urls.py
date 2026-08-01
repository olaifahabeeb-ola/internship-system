from django.urls import path
from . import views

app_name = 'assessment'

urlpatterns = [

    # ── Root entry ───────────────────────────────────────────────
    path('', views.my_assessment, name='index'),

    # ── Supervisor ────────────────────────────────────────────────
    path('dashboard/',
         views.supervisor_dashboard,        name='supervisor_dashboard'),
    path('create/<int:app_pk>/<str:assessment_type>/',
         views.create_assessment,           name='create'),
    path('<int:pk>/',
         views.assessment_detail,           name='detail'),

    # ── Student ───────────────────────────────────────────────────
    path('my-assessments/',
         views.student_assessments,         name='student_assessments'),
    path('<int:pk>/acknowledge/',
         views.acknowledge_assessment,      name='acknowledge'),

    # ── Coordinator ───────────────────────────────────────────────
    path('all/',
         views.coordinator_assessment_list, name='coordinator_list'),
    path('stats/',
         views.coordinator_stats,           name='coordinator_stats'),

    # ── Legacy stubs (used by sidebar links from Phase 1/2) ───────
    path('my/',
         views.my_assessment,               name='my_assessment'),
    path('assess/<int:app_pk>/',
         views.assess_student,              name='assess_student'),
    path('supervisor/',
         views.supervisor_list,             name='supervisor_list'),
]
