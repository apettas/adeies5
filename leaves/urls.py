from django.urls import path
from . import views

app_name = 'leaves'

urlpatterns = [
    # Dashboard redirects
    path('', views.dashboard_redirect, name='dashboard_redirect'),
    
    # Employee URLs
    path('employee/', views.EmployeeDashboardView.as_view(), name='employee_dashboard'),
    path('create/', views.CreateLeaveRequestView.as_view(), name='create_leave_request'),
    
    # Manager URLs
    path('manager/', views.ManagerDashboardView.as_view(), name='manager_dashboard'),
    path('approve/<int:pk>/', views.approve_leave_request, name='approve_leave_request'),
    path('reject/<int:pk>/', views.reject_leave_request, name='reject_leave_request'),
    
    # Handler URLs
    path('handler/', views.HandlerDashboardView.as_view(), name='handler_dashboard'),
    path('complete/<int:pk>/', views.complete_leave_request, name='complete_leave_request'),
    path('reject-handler/<int:pk>/', views.reject_leave_request_by_handler, name='reject_leave_request_by_handler'),
    path('users/', views.UsersListView.as_view(), name='users_list'),
    path('user/<int:user_id>/history/', views.UserLeaveHistoryView.as_view(), name='user_leave_history'),
    
    # Detail view
    path('detail/<int:pk>/', views.LeaveRequestDetailView.as_view(), name='leave_request_detail'),
    
    # Secure file handling
    path('files/<int:file_id>/', views.serve_secure_file, name='serve_secure_file'),
    path('files/<int:file_id>/delete/', views.delete_secure_file, name='delete_secure_file'),
]