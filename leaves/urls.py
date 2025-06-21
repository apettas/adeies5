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
    
    # Detail view
    path('detail/<int:pk>/', views.LeaveRequestDetailView.as_view(), name='leave_request_detail'),
]