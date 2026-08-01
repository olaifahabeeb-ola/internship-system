from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView, RedirectView


urlpatterns = [
    path('admin/', admin.site.urls),

    # Landing page
    path('', TemplateView.as_view(template_name='home.html'), name='home'),

    # Apps
    path('accounts/',      include('accounts.urls',      namespace='accounts')),
    path('placements/',    include('placements.urls',    namespace='placements')),
    path('logbook/',       include('logbook.urls',       namespace='logbook')),
    path('assessment/',    include('assessment.urls',    namespace='assessment')),
    path('announcements/', include('announcements.urls', namespace='announcements')),
    path('reports/',       include('reports.urls',       namespace='reports')),
    path('notifications/', include('notifications.urls', namespace='notifications')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)