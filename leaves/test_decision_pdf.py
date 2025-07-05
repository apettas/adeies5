#!/usr/bin/env python3
"""
Test script για debug του decision PDF functionality
"""
import os
import sys
import django

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pdede_leaves.settings')
django.setup()

from leaves.models import LeaveRequest
from leaves.crypto_utils import SecureFileHandler
from django.conf import settings

def test_decision_pdf_serving():
    """Test decision PDF serving functionality"""
    
    # Find requests with decision PDFs (exclude empty strings)
    requests_with_pdfs = LeaveRequest.objects.filter(
        decision_pdf_path__isnull=False,
        decision_pdf_encryption_key__isnull=False
    ).exclude(
        decision_pdf_path='',
        decision_pdf_encryption_key=''
    )
    
    print(f"Found {requests_with_pdfs.count()} requests with decision PDFs")
    
    for request in requests_with_pdfs:
        print(f"\n--- Testing Request ID: {request.id} ---")
        print(f"Status: {request.status}")
        print(f"Decision PDF Path: {request.decision_pdf_path}")
        print(f"Decision PDF Encryption Key: {request.decision_pdf_encryption_key}")
        print(f"Decision PDF Size: {request.decision_pdf_size}")
        print(f"Has Decision PDF: {request.has_decision_pdf}")
        
        # Check if file exists
        if request.decision_pdf_path.startswith('/') or request.decision_pdf_path.startswith('\\'):
            full_path = request.decision_pdf_path
        else:
            full_path = os.path.join(settings.MEDIA_ROOT, request.decision_pdf_path)
            
        print(f"Full path: {full_path}")
        print(f"File exists: {os.path.exists(full_path)}")
        
        if os.path.exists(full_path):
            print(f"File size on disk: {os.path.getsize(full_path)} bytes")
            
            # Try to decrypt
            try:
                decrypted_content = SecureFileHandler.load_encrypted_file(
                    full_path,
                    request.decision_pdf_encryption_key
                )
                
                if decrypted_content:
                    print(f"✓ Decryption successful! Content size: {len(decrypted_content)} bytes")
                    # Check if it's a PDF
                    if decrypted_content.startswith(b'%PDF'):
                        print("✓ Content is a valid PDF")
                    else:
                        print("✗ Content is NOT a valid PDF")
                        print(f"First 20 bytes: {decrypted_content[:20]}")
                else:
                    print("✗ Decryption returned None")
                    
            except Exception as e:
                print(f"✗ Decryption failed: {e}")
        else:
            print("✗ File does not exist")
        
        print("-" * 50)

if __name__ == "__main__":
    test_decision_pdf_serving()