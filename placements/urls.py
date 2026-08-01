from django.urls import path
from . import views

app_name = 'placements'

urlpatterns = [

    # ── Shared / Student ──────────────────────────────────────────
    path('',                          views.placement_list,   name='list'),
    path('<int:pk>/',                 views.placement_detail, name='detail'),

    # Student-specific
    path('student/apply/<int:pk>/',         views.apply,             name='apply'),
    path('student/my-applications/',        views.my_applications,   name='my_applications'),

    # ── Supervisor ────────────────────────────────────────────────
    path('supervisor/create/',              views.supervisor_create_placement, name='supervisor_create'),
    path('supervisor/my-placements/',       views.supervisor_my_placements,    name='supervisor_my_placements'),

    # ── Coordinator ───────────────────────────────────────────────
    path('coordinator/',                    views.coordinator_list,   name='coordinator_list'),
    path('coordinator/create/',             views.placement_create,   name='create'),
    path('coordinator/<int:pk>/edit/',      views.placement_edit,     name='edit'),
    path('coordinator/<int:pk>/close/',     views.placement_close,    name='close'),
    path('coordinator/<int:pk>/applications/',
         views.coordinator_application_list, name='coordinator_app_list'),
    path('coordinator/applications/',       views.all_applications,   name='all_applications'),
    path('coordinator/applications/<int:pk>/review/',
         views.review_application,          name='review_application'),
    path('coordinator/supervised-students/',views.supervised_students,name='supervised_students'),

    # Placement approval workflow — supervisor submissions awaiting sign-off
    path('coordinator/pending/',            views.coordinator_pending_placements, name='coordinator_pending_placements'),
    path('coordinator/pending/<int:pk>/review/',
         views.review_placement,            name='review_placement'),
]