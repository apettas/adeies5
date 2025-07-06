from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from leaves.models import LeaveRequest, Logo, Info, Ypopsin, Signee
from leaves.crypto_utils import SecureFileHandler
from datetime import datetime
import weasyprint
import os


class Command(BaseCommand):
    help = 'Test PDF generation for decision workflow'

    def add_arguments(self, parser):
        parser.add_argument('--leave-request-id', type=int, default=55,
                          help='Leave request ID to test with')

    def handle(self, *args, **options):
        leave_request_id = options['leave_request_id']
        
        try:
            # Step 1: Load the leave request
            leave_request = LeaveRequest.objects.get(id=leave_request_id)
            self.stdout.write(f'=== Testing PDF generation for request ID: {leave_request.id} ===')
            self.stdout.write(f'User: {leave_request.user.get_full_name()}, Days: {leave_request.days_requested}')
            self.stdout.write(f'Status: {leave_request.status}')
            
            # Step 2: Create context
            context = {
                'leave_request': leave_request,
                'decision_logo': Logo.objects.first(),
                'decision_info': Info.objects.first(),
                'decision_ypopsin': Ypopsin.objects.first(),
                'decision_signee': Signee.objects.first(),
                'final_decision_text': f'Δοκιμαστική απόφαση για {leave_request.days_requested} ημέρες άδειας για τον κ. {leave_request.user.get_full_name()}',
                'generated_date': datetime.now(),
            }
            self.stdout.write(self.style.SUCCESS('✓ Context created successfully'))
            
            # Step 3: Generate HTML
            html_string = render_to_string('leaves/decision_pdf_template.html', context)
            self.stdout.write(self.style.SUCCESS(f'✓ HTML generated: {len(html_string)} characters'))
            
            # Step 4: Generate PDF
            pdf = weasyprint.HTML(string=html_string).write_pdf()
            self.stdout.write(self.style.SUCCESS(f'✓ PDF generated: {len(pdf)} bytes'))
            
            # Step 5: Save and encrypt
            handler = SecureFileHandler()
            decision_dir = f'media/private_media/leave_decisions/{leave_request.id}/'
            os.makedirs(decision_dir, exist_ok=True)
            
            pdf_filename = f'decision_{leave_request.id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
            pdf_path = os.path.join(decision_dir, pdf_filename)
            
            encrypted_path, encryption_key = handler.save_encrypted_bytes(pdf, pdf_path)
            self.stdout.write(self.style.SUCCESS(f'✓ PDF saved and encrypted: {encrypted_path}'))
            
            # Step 6: Update LeaveRequest
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
            
            self.stdout.write(self.style.SUCCESS('✓ LeaveRequest updated with decision data'))
            self.stdout.write(f'  - PDF path: {leave_request.decision_pdf_path}')
            self.stdout.write(f'  - PDF size: {leave_request.decision_pdf_size} bytes')
            self.stdout.write(f'  - Has decision PDF: {leave_request.has_decision_pdf()}')
            
            self.stdout.write(self.style.SUCCESS('=== PDF Generation Test COMPLETED SUCCESSFULLY! ==='))
            
        except LeaveRequest.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'LeaveRequest with ID {leave_request_id} does not exist'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ PDF generation failed: {e}'))
            import traceback
            traceback.print_exc()