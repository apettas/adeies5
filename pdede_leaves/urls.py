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
from accounts.views import PdedeCASLoginView, logout_view, alt_login_view
from django_cas_ng import views as cas_views
from django.views.generic import RedirectView


def health_check(request):
    return HttpResponse("healthy", content_type="text/plain")


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect('leaves:dashboard_redirect')
    return redirect('accounts:login')


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_redirect, name='home'),
    path('logout/', logout_view, name='root_logout'),
    path('alt/', alt_login_view, name='alt_login'),
    path('login/', include('accounts.urls')),
    path('leaves/', include('leaves.urls')),
    path('notifications/', include('notifications.urls')),
    path('health/', health_check, name='health_check'),
]

# CAS URLs — only if CAS is configured
if config('CAS_SERVER_URL', default=''):
    # Το ΠΣΔ καταχωρεί ως service URL το /login/cas/callback/
    urlpatterns += [
        path('login/cas/callback/', PdedeCASLoginView.as_view(), name='cas_ng_login'),
        path(
            'login/cas/login/',
            RedirectView.as_view(url='/login/cas/callback/', permanent=False),
        ),
        path('login/cas/logout/', cas_views.LogoutView.as_view(), name='cas_ng_logout'),
    ]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)