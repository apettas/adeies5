"""
URL configuration for pdede_leaves project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.http import HttpResponse


def health_check(request):
    return HttpResponse("healthy", content_type="text/plain")


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect('leaves:dashboard_redirect')
    return redirect('accounts:login')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_redirect, name='home'),
    path('login/', include('accounts.urls')),
    path('leaves/', include('leaves.urls')),
    path('notifications/', include('notifications.urls')),
    path('health/', health_check, name='health_check'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)