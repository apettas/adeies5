"""
URL configuration for pdede_leaves project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.http import HttpResponse
from decouple import config
from accounts.views import PdedeCASLoginView
from django_cas_ng import views as cas_views


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

# CAS URLs — only if CAS is configured
if config('CAS_SERVER_URL', default=''):
    urlpatterns += [
        path('login/cas/login/', PdedeCASLoginView.as_view(), name='cas_ng_login'),
        path('login/cas/callback/', cas_views.CallbackView.as_view(), name='cas_ng_callback'),
        path('login/cas/logout/', cas_views.LogoutView.as_view(), name='cas_ng_logout'),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)