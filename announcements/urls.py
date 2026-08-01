from django.urls import path
from . import views

app_name = 'announcements'

urlpatterns = [
    # Shared
    path('',                          views.announcement_list,    name='list'),
    path('<int:pk>/',                  views.announcement_detail,  name='detail'),

    # Coordinator
    path('create/',                    views.coordinator_create,   name='create'),
    path('manage/',                    views.coordinator_list,     name='coordinator_list'),
    path('<int:pk>/edit/',             views.coordinator_edit,     name='edit'),
    path('<int:pk>/delete/',           views.coordinator_delete,   name='delete'),
    path('<int:pk>/toggle/',           views.coordinator_toggle,   name='toggle'),
]
