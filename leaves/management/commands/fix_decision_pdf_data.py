from django.core.management.base import BaseCommand
from django.utils import timezone
from leaves.models import LeaveRequest
import os
from django.conf import settings

class Command(BaseCommand):
    help = 'Fix decision PDF data for existing requests'

    def add_arguments(self, parser):
        parser.add_argument('--request-id', type=int, help='Leave request ID to fix')

    def handle(self, *args, **options):
        request_id = options.get('request_id')
        
        if request_id:
            try:
                leave_request = LeaveRequest.objects.get(id=request_id)
                
                # Check if decision PDF files exist
                decision_dir = os.path.join(settings.MEDIA_ROOT, 'private_media', 'leave_decisions', str(leave_request.id))
                
                if os.path.exists(decision_dir):
                    # Find the most recent decision PDF
                    pdf_files = [f for f in os.listdir(decision_dir) if f.endswith('.pdf')]
                    
                    if pdf_files:
                        latest_pdf = max(pdf_files, key=lambda x: os.path.getctime(os.path.join(decision_dir, x)))
                        pdf_path = os.path.join(decision_dir, latest_pdf)
                        pdf_size = os.path.getsize(pdf_path)
                        
                        # Generate a dummy encryption key (for testing)
                        from leaves.crypto_utils import SecureFileHandler
                        dummy_key = SecureFileHandler.generate_key()
                        
                        # Update the leave request
                        leave_request.decision_pdf_path = pdf_path
                        leave_request.decision_pdf_encryption_key = dummy_key.hex()
                        leave_request.decision_pdf_size = pdf_size
                        
                        leave_request.save()
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Successfully updated leave request {request_id} with decision PDF data'
                            )
                        )
                        
                        # Check if it was saved correctly
                        updated_request = LeaveRequest.objects.get(id=request_id)
                        self.stdout.write(f'has_decision_pdf: {updated_request.has_decision_pdf}')
                        self.stdout.write(f'decision_pdf_path: {updated_request.decision_pdf_path}')
                        
                    else:
                        self.stdout.write(
                            self.style.ERROR(f'No PDF files found in {decision_dir}')
                        )
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Decision directory not found: {decision_dir}')
                    )
                    
            except LeaveRequest.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Leave request with ID {request_id} not found')
                )
        else:
            self.stdout.write(
                self.style.ERROR('Please provide --request-id argument')
            )