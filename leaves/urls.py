from django.urls import path
from . import views
from .decision_views import (
    prepare_decision_preview, generate_final_decision_pdf, serve_decision_pdf,
    upload_exact_copy_pdf, serve_exact_copy_pdf, complete_leave_request_final,
    send_to_signatures_view
)
from .calendar_views import leave_calendar_view
from .balance_views import balance_ledger_view, manual_balance_adjustment
from .base_data_views import BaseDataIndexView, BaseDataTableView, GetRecordDataView
from accounts.handler_registration_views import (
    PendingUserRegistrationsListView,
    PendingUserRegistrationReviewView,
    acknowledge_pending_registration,
    reject_pending_registration,
)

app_name = 'leaves'

urlpatterns = [
    # Dashboard redirects
    path('', views.dashboard_redirect, name='dashboard_redirect'),
    
    # Employee URLs
    path('employee/', views.EmployeeDashboardView.as_view(), name='employee_dashboard'),
    path('create/', views.CreateLeaveRequestView.as_view(), name='create_leave_request'),
    path('create-atypical/', views.CreateAtypicalLeaveView.as_view(), name='create_atypical_leave'),
    path('create-for-user/<int:user_id>/', views.create_leave_for_user, name='create_leave_for_user'),
    path('submit_final/', views.submit_final_request, name='submit_final_request'),
    path('download_pdf/<int:request_id>/', views.download_leave_pdf, name='download_leave_pdf'),
    path('withdraw/<int:pk>/', views.withdraw_leave_request, name='withdraw_leave_request'),
    
    # Manager URLs
    path('manager/', views.ManagerDashboardView.as_view(), name='manager_dashboard'),
    path('calendar/', leave_calendar_view, name='calendar'),
    path('calendar/<int:year>/<int:month>/', leave_calendar_view, name='calendar'),
    path('approve/<int:pk>/', views.approve_leave_request, name='approve_leave_request'),
    path('reject/<int:pk>/', views.reject_leave_request, name='reject_leave_request'),
    
    # Handler URLs
    path('handler/', views.HandlerDashboardView.as_view(), name='handler_dashboard'),
    path('complete/<int:pk>/', views.complete_leave_request, name='complete_leave_request'),
    path('reject-handler/<int:pk>/', views.reject_leave_request_by_handler, name='reject_leave_request_by_handler'),
    path('send-to-protocol/<int:pk>/', views.send_to_protocol_pdede, name='send_to_protocol_pdede'),
    path('upload-protocol-pdf/<int:pk>/', views.upload_protocol_pdf, name='upload_protocol_pdf'),
    path('request-documents/<int:pk>/', views.request_documents, name='request_documents'),
    path('send-documents-email/<int:pk>/', views.send_documents_email, name='send_documents_email'),
    path('provide-documents/<int:pk>/', views.provide_documents, name='provide_documents'),
    path('return-to-employee/<int:pk>/', views.return_leave_to_employee, name='return_leave_to_employee'),
    path('handler-upload-attachment/<int:pk>/', views.handler_upload_attachment, name='handler_upload_attachment'),
    path('users/', views.UsersListView.as_view(), name='users_list'),
    path('pending-registrations/', PendingUserRegistrationsListView.as_view(), name='pending_user_registrations'),
    path(
        'pending-registrations/<int:user_id>/',
        PendingUserRegistrationReviewView.as_view(),
        name='pending_user_registration_review',
    ),
    path(
        'pending-registration-acknowledge/<int:user_id>/',
        acknowledge_pending_registration,
        name='acknowledge_pending_registration',
    ),
    path(
        'pending-registration-reject/<int:user_id>/',
        reject_pending_registration,
        name='reject_pending_registration',
    ),
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
    path('decision/send-to-signatures/<int:pk>/', send_to_signatures_view, name='send_to_signatures'),
    
    # Exact Copy URLs
    path('exact-copy/upload/<int:pk>/', upload_exact_copy_pdf, name='upload_exact_copy_pdf'),
    path('exact-copy-pdf/<int:pk>/', serve_exact_copy_pdf, name='serve_exact_copy_pdf'),
    path('complete-final/<int:pk>/', complete_leave_request_final, name='complete_leave_request_final'),
    
    # Secure file handling
    path('files/<int:file_id>/', views.serve_secure_file, name='serve_secure_file'),
    path('files/<int:file_id>/delete/', views.delete_secure_file, name='delete_secure_file'),
    path('protocol-pdf/<int:pk>/', views.serve_protocol_pdf, name='serve_protocol_pdf'),

    # Locking mechanism
    path('lock/<int:pk>/', views.lock_leave_request, name='lock_leave_request'),
    path('unlock/<int:pk>/', views.unlock_leave_request, name='unlock_leave_request'),

    # Delete by handler
    path('delete/<int:pk>/', views.delete_leave_request, name='delete_leave_request'),

    # Withdraw completed leave
    path('withdraw-completed/<int:pk>/', views.withdraw_completed_leave, name='withdraw_completed_leave'),

    # Merged PDF & Send to Protocol (email)
    path('send-to-protocol-email/<int:pk>/', views.send_to_protocol_view, name='send_to_protocol'),
    path('merged-pdf/<int:pk>/', views.serve_merged_pdf, name='serve_merged_pdf'),

    # YC Committee workflow
    path('yc-referral/<int:pk>/', views.send_to_yc_committee, name='send_to_yc_committee'),
    path('yc-decision/<int:pk>/', views.receive_from_yc_committee, name='receive_from_yc_committee'),
    path('yc-acknowledge/<int:user_id>/', views.acknowledge_yc_alert, name='acknowledge_yc_alert'),
    path('document-upload-acknowledge/<int:pk>/', views.acknowledge_document_upload, name='acknowledge_document_upload'),
    path('submit-applicant-documents/<int:pk>/', views.submit_applicant_documents, name='submit_applicant_documents'),
    path(
        'document-submission-acknowledge/<int:pk>/',
        views.acknowledge_document_submission,
        name='acknowledge_document_submission',
    ),
    
    # Attendance sheet
    path('attendance/', views.attendance_sheet, name='attendance_sheet'),
    
    # Balance Ledger
    path('balance-ledger/<int:user_id>/', balance_ledger_view, name='balance_ledger'),
    path('balance-adjustment/<int:user_id>/', manual_balance_adjustment, name='manual_balance_adjustment'),
    
    # Base Data Management
    path('base-data/', BaseDataIndexView.as_view(), name='base_data_index'),
    path('base-data/<str:table_key>/', BaseDataTableView.as_view(), name='base_data_table'),
    path('base-data/<str:table_key>/record/<int:record_id>/', GetRecordDataView.as_view(), name='get_record_data'),
]
