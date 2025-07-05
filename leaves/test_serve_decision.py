#!/usr/bin/env python3
"""
Test script για το serve_decision_pdf view
"""
import os
import sys
import django

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from leaves.models import LeaveRequest
from leaves.views import serve_decision_pdf

User = get_user_model()

def test_serve_decision_pdf():
    """Test the serve_decision_pdf view directly"""
    
    # Get a request with decision PDF
    request = LeaveRequest.objects.get(id=59)
    print(f"Testing request {request.id}")
    print(f"Has decision PDF: {request.has_decision_pdf}")
    
    # Get a user who should have access
    user = User.objects.filter(roles__code='HR_OFFICER').first()
    if not user:
        user = User.objects.filter(roles__code='administrator').first()
    if not user:
        user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = request.user
    
    print(f"Testing with user: {user.username} (handler: {user.is_leave_handler})")
    
    # Create a mock request
    factory = RequestFactory()
    mock_request = factory.get(f'/leaves/decision-pdf/{request.id}/')
    mock_request.user = user
    
    try:
        response = serve_decision_pdf(mock_request, request.id)
        print(f"✓ Response status: {response.status_code}")
        print(f"✓ Content type: {response.get('Content-Type')}")
        print(f"✓ Content length: {response.get('Content-Length')}")
        print(f"✓ Content disposition: {response.get('Content-Disposition')}")
        
        # Check if content is a PDF
        content = response.content
        if content.startswith(b'%PDF'):
            print("✓ Content is a valid PDF")
        else:
            print("✗ Content is not a valid PDF")
            print(f"First 50 bytes: {content[:50]}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_serve_decision_pdf()