from django.urls import path
from . import views
from .decision_views import (
    prepare_decision_preview, generate_final_decision_pdf, serve_decision_pdf,
    upload_exact_copy_pdf, serve_exact_copy_pdf, complete_leave_request_final
)

app_name = 'leaves'

urlpatterns = [
    # Dashboard redirects
    path('', views.dashboard_redirect, name='dashboard_redirect'),
    
    # Employee URLs
    path('employee/', views.EmployeeDashboardView.as_view(), name='employee_dashboard'),
    path('create/', views.CreateLeaveRequestView.as_view(), name='create_leave_request'),
    path('submit_final/', views.submit_final_request, name='submit_final_request'),
    path('download_pdf/<int:request_id>/', views.download_leave_pdf, name='download_leave_pdf'),
    
    # Manager URLs
    path('manager/', views.ManagerDashboardView.as_view(), name='manager_dashboard'),
    path('approve/<int:pk>/', views.approve_leave_request, name='approve_leave_request'),
    path('reject/<int:pk>/', views.reject_leave_request, name='reject_leave_request'),
    
    # Handler URLs
    path('handler/', views.HandlerDashboardView.as_view(), name='handler_dashboard'),
    path('complete/<int:pk>/', views.complete_leave_request, name='complete_leave_request'),
    path('reject-handler/<int:pk>/', views.reject_leave_request_by_handler, name='reject_leave_request_by_handler'),
    path('send-to-protocol/<int:pk>/', views.send_to_protocol_pdede, name='send_to_protocol_pdede'),
    path('upload-protocol-pdf/<int:pk>/', views.upload_protocol_pdf, name='upload_protocol_pdf'),
    path('users/', views.UsersListView.as_view(), name='users_list'),
    path('user/<int:user_id>/history/', views.UserLeaveHistoryView.as_view(), name='user_leave_history'),
    
    # Secretary URLs (ΚΕΔΑΣΥ/ΚΕΠΕΑ)
    path('secretary/', views.SecretaryDashboardView.as_view(), name='secretary_dashboard'),
    path('add-kedasy-kepea-protocol/<int:pk>/', views.add_kedasy_kepea_protocol, name='add_kedasy_kepea_protocol'),
    
    # Detail view
    path('detail/<int:pk>/', views.LeaveRequestDetailView.as_view(), name='leave_request_detail'),
    path('detail/<int:pk>/', views.LeaveRequestDetailView.as_view(), name='detail'),  # Alias for compatibility
    
    # Decision PDF URLs
    path('decision/prepare/<int:leave_request_id>/', prepare_decision_preview, name='prepare_decision_preview'),
    path('decision/generate/', generate_final_decision_pdf, name='generate_final_decision_pdf'),
    path('decision-pdf/<int:pk>/', serve_decision_pdf, name='serve_decision_pdf'),
    
    # Exact Copy URLs
    path('exact-copy/upload/<int:pk>/', upload_exact_copy_pdf, name='upload_exact_copy_pdf'),
    path('exact-copy-pdf/<int:pk>/', serve_exact_copy_pdf, name='serve_exact_copy_pdf'),
    path('complete-final/<int:pk>/', complete_leave_request_final, name='complete_leave_request_final'),
    
    # Secure file handling
    path('files/<int:file_id>/', views.serve_secure_file, name='serve_secure_file'),
    path('files/<int:file_id>/delete/', views.delete_secure_file, name='delete_secure_file'),
    path('protocol-pdf/<int:pk>/', views.serve_protocol_pdf, name='serve_protocol_pdf'),
]