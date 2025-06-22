from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('registration-pending/', views.registration_pending_view, name='registration_pending'),
    path('check-status/', views.registration_status_view, name='registration_status'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('manage-roles/', views.UserRoleManagementView.as_view(), name='manage_roles'),
    path('assign-role/', views.assign_role, name='assign_role'),
    path('update-department/', views.update_user_department, name='update_department'),
]