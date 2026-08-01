from django.urls import path
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/',              views.register_view,                name='register'),
    path('login/',                 views.login_view,                   name='login'),
    path('logout/',                views.logout_view,                  name='logout'),
    path('dashboard/',             views.dashboard_view,               name='dashboard'),
    path('dashboard/admin/',       views.admin_dashboard,              name='admin_dashboard'),
    path('dashboard/student/',     views.student_dashboard,            name='student_dashboard'),
    path('dashboard/supervisor/',  views.supervisor_dashboard,         name='supervisor_dashboard'),
    path('dashboard/coordinator/', views.coordinator_dashboard,        name='coordinator_dashboard'),
    path('profile/',               views.profile_view,                 name='profile'),
    path('students/by-department/',views.coordinator_students_by_dept, name='students_by_dept'),
    path('students/bulk-upload/',  views.bulk_upload_students,         name='bulk_upload'),

    # ── Password reset (Django's built-in views, our templates) ───────
    path('password-reset/', auth_views.PasswordResetView.as_view(
            template_name='accounts/password_reset_form.html',
            email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done'),
        ), name='password_reset'),

    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
            template_name='accounts/password_reset_done.html',
        ), name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url=reverse_lazy('accounts:password_reset_complete'),
        ), name='password_reset_confirm'),

    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
            template_name='accounts/password_reset_complete.html',
        ), name='password_reset_complete'),
]