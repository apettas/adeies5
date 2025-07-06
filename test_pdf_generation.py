#!/usr/bin/env python
import os
import sys
import django
from datetime import datetime

# Django setup - εδώ είμαι μέσα στο Docker container
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'adeiesmvp5.settings')
django.setup()

from django.template.loader import render_to_string
from leaves.models import LeaveRequest, Logo, Info, Ypopsin, Signee
from leaves.crypto_utils import SecureFileHandler
import weasyprint

def test_pdf_generation():
    print("Starting PDF Generation Test...")
    
    # Παίρνω την αίτηση ID 55
    try:
        leave_request = LeaveRequest.objects.get(id=55)
        print(f"✓ Found request ID: {leave_request.id}, Status: {leave_request.status}")
        print(f"  User: {leave_request.user.get_full_name()}, Days: {leave_request.days_requested}")
    except LeaveRequest.DoesNotExist:
        print("✗ Request ID 55 not found")
        return False
    
    # Δημιουργώ το context
    context = {
        'leave_request': leave_request,
        'decision_logo': Logo.objects.first(),
        'decision_info': Info.objects.first(),
        'decision_ypopsin': Ypopsin.objects.first(),
        'decision_signee': Signee.objects.first(),
        'final_decision_text': f'Δοκιμαστική απόφαση για {leave_request.days_requested} ημέρες άδειας για τον κ. {leave_request.user.get_full_name()}',
        'generated_date': datetime.now(),
    }
    
    try:
        # 1. HTML Generation
        html_string = render_to_string('leaves/decision_pdf_template.html', context)
        print(f"✓ HTML generated: {len(html_string)} characters")
        
        # 2. PDF Generation με WeasyPrint
        pdf = weasyprint.HTML(string=html_string).write_pdf()
        print(f"✓ PDF generated: {len(pdf)} bytes")
        
        # 3. Αποθήκευση και κρυπτογράφηση
        handler = SecureFileHandler()
        
        # Δημιουργώ το directory αν δεν υπάρχει
        decision_dir = f'media/private_media/leave_decisions/{leave_request.id}/'
        os.makedirs(decision_dir, exist_ok=True)
        
        # Αποθηκεύω το PDF
        pdf_filename = f'decision_{leave_request.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        pdf_path = os.path.join(decision_dir, pdf_filename)
        
        encrypted_path, encryption_key = handler.save_encrypted_file(pdf, pdf_path)
        print(f"✓ PDF saved and encrypted: {encrypted_path}")
        
        # 4. Ενημερώνω το LeaveRequest
        leave_request.decision_logo = Logo.objects.first()
        leave_request.decision_info = Info.objects.first()
        leave_request.decision_ypopsin = Ypopsin.objects.first()
        leave_request.decision_signee = Signee.objects.first()
        leave_request.final_decision_text = context['final_decision_text']
        leave_request.decision_pdf_path = encrypted_path
        leave_request.decision_pdf_encryption_key = encryption_key
        leave_request.decision_pdf_size = len(pdf)
        leave_request.decision_created_at = datetime.now()
        leave_request.save()
        
        print(f"✓ LeaveRequest updated with decision data")
        print(f"  - PDF path: {leave_request.decision_pdf_path}")
        print(f"  - PDF size: {leave_request.decision_pdf_size} bytes")
        print(f"  - Has decision PDF: {leave_request.has_decision_pdf()}")
        
        return True
        
    except Exception as e:
        print(f"✗ PDF generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pdf_generation()
    if success:
        print("\n🎉 PDF Generation Test PASSED!")
    else:
        print("\n❌ PDF Generation Test FAILED!")