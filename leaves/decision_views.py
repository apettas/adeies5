from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.contrib import messages
from django.urls import reverse
import os
from datetime import datetime

from leaves.models import LeaveRequest, Logo, Info, Ypopsin, Signee
from leaves.crypto_utils import SecureFileHandler


@login_required
def prepare_decision_preview(request, leave_request_id):
    """
    Προεπισκόπηση και επεξεργασία απόφασης
    """
    # Έλεγχος δικαιωμάτων
    if not request.user.is_leave_handler:
        messages.error(request, 'Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.')
        return redirect('leaves:dashboard_redirect')
    
    leave_request = get_object_or_404(LeaveRequest, id=leave_request_id)
    
    # Έλεγχος αν μπορεί να δημιουργηθεί απόφαση
    if not leave_request.can_create_decision():
        messages.error(request, 'Δεν μπορεί να δημιουργηθεί απόφαση για αυτή την αίτηση.')
        return redirect('leaves:detail', pk=leave_request.id)
    
    # Φόρτωση δεδομένων από βάση
    logos = Logo.objects.filter(is_active=True)
    infos = Info.objects.filter(is_active=True)
    ypopsins = Ypopsin.objects.filter(is_active=True)
    signees = Signee.objects.filter(is_active=True)
    
    # Δημιουργία default δεδομένων αν δεν υπάρχουν
    if not logos.exists():
        default_logo = Logo.objects.create(
            logo_short="ΕΛΛΗΝΙΚΗ ΔΗΜΟΚΡΑΤΙΑ",
            logo="ΕΛΛΗΝΙΚΗ ΔΗΜΟΚΡΑΤΙΑ\nΠΕΡΙΦΕΡΕΙΑΚΗ ΔΙΕΥΘΥΝΣΗ ΕΚΠΑΙΔΕΥΣΗΣ\nΔΥΤΙΚΗΣ ΕΛΛΑΔΑΣ",
            is_active=True
        )
        logos = Logo.objects.filter(is_active=True)
    
    if not infos.exists():
        default_info = Info.objects.create(
            info_short="Πληροφορίες ΠΔΕΔΕ",
            info="Στοιχεία Χειριστή Αδειών:\nΠεριφερειακή Διεύθυνση Εκπαίδευσης Δυτικής Ελλάδας\nΤμήμα Διοικητικού",
            is_active=True
        )
        infos = Info.objects.filter(is_active=True)
    
    if not ypopsins.exists():
        default_ypopsin = Ypopsin.objects.create(
            ypopsin_short="Νομοθεσία Αδειών",
            ypopsin="1. Τις διατάξεις του Ν. 3528/2007\n2. Τις σχετικές εγκυκλίους\n3. Την αίτηση του/της ενδιαφερομένου/ης",
            is_active=True
        )
        ypopsins = Ypopsin.objects.filter(is_active=True)
    
    if not signees.exists():
        default_signee = Signee.objects.create(
            signee_short="Διευθυντής ΠΔΕΔΕ",
            signee_name="Ο/Η Περιφερειακός/ή Διευθυντής/ντρια",
            signee="Ο/Η Περιφερειακός/ή Διευθυντής/ντρια\nΕκπαίδευσης Δυτικής Ελλάδας\n\n\n(Υπογραφή)",
            is_active=True
        )
        signees = Signee.objects.filter(is_active=True)
    
    # Προεπιλεγμένα δεδομένα
    default_logo = leave_request.decision_logo or logos.first()
    default_info = leave_request.decision_info or infos.first()
    default_ypopsin = leave_request.decision_ypopsin or ypopsins.first()
    default_signee = leave_request.decision_signee or signees.first()
    
    context = {
        'leave_request': leave_request,
        'logos': logos,
        'infos': infos,
        'ypopsins': ypopsins,
        'signees': signees,
        'default_logo': default_logo,
        'default_info': default_info,
        'default_ypopsin': default_ypopsin,
        'default_signee': default_signee,
        'final_decision_text': leave_request.final_decision_text or '',
    }
    
    return render(request, 'leaves/decision_preview.html', context)


@login_required
def generate_final_decision_pdf(request):
    """
    Δημιουργία τελικού PDF απόφασης
    """
    # Έλεγχος δικαιωμάτων
    if not request.user.is_leave_handler:
        messages.error(request, 'Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.')
        return redirect('leaves:dashboard_redirect')
    
    if request.method != 'POST':
        messages.error(request, 'Μη έγκυρη μέθοδος.')
        return redirect('leaves:handler_dashboard')
    
    # Λήψη δεδομένων από φόρμα
    leave_request_id = request.POST.get('leave_request_id')
    leave_request = get_object_or_404(LeaveRequest, id=leave_request_id)
    
    # Έλεγχος αν μπορεί να δημιουργηθεί απόφαση
    if not leave_request.can_create_decision():
        messages.error(request, 'Δεν μπορεί να δημιουργηθεί απόφαση για αυτή την αίτηση.')
        return redirect('leaves:detail', pk=leave_request.id)
    
    try:
        # Έλεγχος διαθεσιμότητας WeasyPrint
        try:
            from weasyprint import HTML
        except ImportError:
            messages.error(request, 'Η δημιουργία PDF δεν είναι διαθέσιμη. Παρακαλώ επικοινωνήστε με τον διαχειριστή.')
            return redirect('leaves:detail', pk=leave_request.id)
        
        # Συλλογή δεδομένων από φόρμα
        logo_id = request.POST.get('logo_id')
        info_id = request.POST.get('info_id')
        ypopsin_id = request.POST.get('ypopsin_id')
        signee_id = request.POST.get('signee_id')
        
        # Επεξεργασμένα κείμενα
        edited_info_text = request.POST.get('info_text', '')
        edited_ypopsin_text = request.POST.get('ypopsin_text', '')
        edited_signee_text = request.POST.get('signee_text', '')
        
        # Λήψη αντικειμένων
        logo = get_object_or_404(Logo, id=logo_id) if logo_id else None
        info = get_object_or_404(Info, id=info_id) if info_id else None
        ypopsin = get_object_or_404(Ypopsin, id=ypopsin_id) if ypopsin_id else None
        signee = get_object_or_404(Signee, id=signee_id) if signee_id else None
        
        # Ενημέρωση LeaveRequest
        leave_request.decision_logo = logo
        leave_request.decision_info = info
        leave_request.decision_ypopsin = ypopsin
        leave_request.decision_signee = signee
        leave_request.final_decision_text = f"Info: {edited_info_text}\nYpopsin: {edited_ypopsin_text}\nSignee: {edited_signee_text}"
        leave_request.decision_created_at = timezone.now()
        
        # Αυτόματη αλλαγή στάτους - δεν θέτουμε processed_by/processed_at ακόμα
        leave_request.status = 'UNDER_PROCESSING'
        leave_request.save()
        
        # Προετοιμασία context για PDF
        context = {
            'leave_request': leave_request,
            'logo': logo,
            'info_text': edited_info_text or (info.info if info else ''),
            'ypopsin_text': edited_ypopsin_text or (ypopsin.ypopsin if ypopsin else ''),
            'signee_text': edited_signee_text or (signee.signee if signee else ''),
            'current_date': timezone.now().strftime('%d/%m/%Y'),
        }
        
        # Δημιουργία HTML από template
        html_string = render_to_string('leaves/decision_pdf_template.html', context)
        
        # Δημιουργία PDF
        html = HTML(string=html_string)
        pdf_content = html.write_pdf()
        
        # Αποθήκευση PDF
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'decision_{leave_request.id}_{timestamp}.pdf'
        
        # Δημιουργία directory αν δεν υπάρχει
        pdf_dir = os.path.join('media', 'private_media', 'leave_decisions', str(leave_request.id))
        os.makedirs(pdf_dir, exist_ok=True)
        
        # Κρυπτογράφηση και αποθήκευση με τη νέα μέθοδο
        pdf_path = os.path.join(pdf_dir, filename)
        handler = SecureFileHandler()
        encrypted_path, encryption_key = handler.save_encrypted_bytes(pdf_content, pdf_path)
        
        # Ενημέρωση των πεδίων PDF
        leave_request.decision_pdf_path = encrypted_path
        leave_request.decision_pdf_encryption_key = encryption_key
        leave_request.decision_pdf_size = len(pdf_content)
        leave_request.save()
        
        messages.success(request, 'Η απόφαση PDF δημιουργήθηκε επιτυχώς!')
        
        # Επιστροφή PDF στον χρήστη
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        messages.error(request, f'Σφάλμα κατά τη δημιουργία της απόφασης: {str(e)}')
        return redirect('leaves:detail', pk=leave_request.id)


@login_required
def serve_decision_pdf(request, pk):
    """
    Σερβίρισμα κρυπτογραφημένου PDF απόφασης
    """
    # Έλεγχος δικαιωμάτων - επιτρέπουμε σε όλους τους χρήστες που μπορούν να δουν την αίτηση
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if not leave_request.can_user_view(request.user):
        messages.error(request, 'Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.')
        return redirect('leaves:dashboard_redirect')
    
    # Έλεγχος αν υπάρχει PDF απόφασης
    if not leave_request.has_decision_pdf():
        messages.error(request, 'Δεν υπάρχει PDF απόφασης για αυτή την αίτηση.')
        return redirect('leaves:detail', pk=leave_request.id)
    
    try:
        # Αποκρυπτογράφηση PDF
        handler = SecureFileHandler()
        pdf_content = handler.load_encrypted_file(leave_request.decision_pdf_path, leave_request.decision_pdf_encryption_key)
        
        if pdf_content is None:
            messages.error(request, 'Δεν ήταν δυνατή η φόρτωση του PDF της απόφασης.')
            return redirect('leaves:detail', pk=leave_request.id)
        
        # Έλεγχος αν είναι για download ή preview
        is_download = request.GET.get('download') == '1'
        
        # Δημιουργία response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        
        if is_download:
            # Για download
            response['Content-Disposition'] = f'attachment; filename="decision_{leave_request.id}.pdf"'
        else:
            # Για preview στο browser
            response['Content-Disposition'] = f'inline; filename="decision_{leave_request.id}.pdf"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Σφάλμα κατά τη φόρτωση του PDF: {str(e)}')
        return redirect('leaves:detail', pk=leave_request.id)


@login_required
def upload_exact_copy_pdf(request, pk):
    """
    Αποστολή ακριβούς αντιγράφου PDF από ΣΗΔΕ
    """
    # Έλεγχος δικαιωμάτων
    if not request.user.is_leave_handler:
        messages.error(request, 'Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.')
        return redirect('leaves:dashboard_redirect')
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος αν μπορεί να ανέβει ακριβές αντίγραφο
    if not leave_request.can_upload_exact_copy():
        messages.error(request, 'Δεν μπορεί να ανέβει ακριβές αντίγραφο για αυτή την αίτηση.')
        return redirect('leaves:detail', pk=leave_request.id)
    
    if request.method == 'POST':
        exact_copy_file = request.FILES.get('exact_copy_pdf')
        
        if not exact_copy_file:
            messages.error(request, 'Παρακαλώ επιλέξτε αρχείο PDF.')
            return redirect('leaves:detail', pk=leave_request.id)
        
        # Έλεγχος τύπου αρχείου
        if not exact_copy_file.name.lower().endswith('.pdf'):
            messages.error(request, 'Το αρχείο πρέπει να είναι PDF.')
            return redirect('leaves:detail', pk=leave_request.id)
        
        # Έλεγχος μεγέθους (max 10MB)
        if exact_copy_file.size > 10 * 1024 * 1024:
            messages.error(request, 'Το αρχείο είναι πολύ μεγάλο. Μέγιστο μέγεθος: 10MB.')
            return redirect('leaves:detail', pk=leave_request.id)
        
        try:
            # Αποθήκευση κρυπτογραφημένου αρχείου
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'exact_copy_{leave_request.id}_{timestamp}.pdf'
            
            # Δημιουργία directory
            pdf_dir = os.path.join('media', 'private_media', 'exact_copies', str(leave_request.id))
            os.makedirs(pdf_dir, exist_ok=True)
            
            # Αποθήκευση κρυπτογραφημένου αρχείου
            pdf_path = os.path.join(pdf_dir, filename)
            handler = SecureFileHandler()
            file_content = exact_copy_file.read()
            encrypted_path, encryption_key = handler.save_encrypted_bytes(file_content, pdf_path)
            
            # Ενημέρωση αίτησης
            leave_request.exact_copy_pdf_path = encrypted_path
            leave_request.exact_copy_pdf_encryption_key = encryption_key
            leave_request.exact_copy_pdf_size = len(file_content)
            leave_request.exact_copy_uploaded_at = timezone.now()
            leave_request.exact_copy_uploaded_by = request.user
            leave_request.save()
            
            messages.success(request, 'Το ακριβές αντίγραφο ανέβηκε επιτυχώς!')
            
        except Exception as e:
            messages.error(request, f'Σφάλμα κατά την αποστολή του αρχείου: {str(e)}')
    
    return redirect('leaves:detail', pk=leave_request.id)


@login_required
def serve_exact_copy_pdf(request, pk):
    """
    Σερβίρισμα ακριβούς αντιγράφου PDF
    """
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος δικαιωμάτων
    if not leave_request.can_user_view(request.user):
        messages.error(request, 'Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.')
        return redirect('leaves:dashboard_redirect')
    
    # Έλεγχος αν υπάρχει ακριβές αντίγραφο
    if not leave_request.has_exact_copy_pdf():
        messages.error(request, 'Δεν υπάρχει ακριβές αντίγραφο για αυτή την αίτηση.')
        return redirect('leaves:detail', pk=leave_request.id)
    
    try:
        # Φόρτωση και αποκρυπτογράφηση PDF
        handler = SecureFileHandler()
        pdf_content = handler.load_encrypted_file(leave_request.exact_copy_pdf_path, leave_request.exact_copy_pdf_encryption_key)
        
        if pdf_content is None:
            messages.error(request, 'Δεν ήταν δυνατή η φόρτωση του ακριβούς αντιγράφου.')
            return redirect('leaves:detail', pk=leave_request.id)
        
        # Έλεγχος αν είναι για download ή preview
        is_download = request.GET.get('download') == '1'
        
        # Δημιουργία response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        
        if is_download:
            response['Content-Disposition'] = f'attachment; filename="exact_copy_{leave_request.id}.pdf"'
        else:
            response['Content-Disposition'] = f'inline; filename="exact_copy_{leave_request.id}.pdf"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Σφάλμα κατά τη φόρτωση του PDF: {str(e)}')
        return redirect('leaves:detail', pk=leave_request.id)


@login_required
def complete_leave_request_final(request, pk):
    """
    Τελική ολοκλήρωση αίτησης (μόνο όταν υπάρχει ακριβές αντίγραφο)
    """
    # Έλεγχος δικαιωμάτων
    if not request.user.is_leave_handler:
        messages.error(request, 'Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.')
        return redirect('leaves:dashboard_redirect')
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    # Έλεγχος αν μπορεί να ολοκληρωθεί
    if not leave_request.can_complete_request():
        messages.error(request, 'Δεν μπορεί να ολοκληρωθεί η αίτηση. Απαιτείται ακριβές αντίγραφο.')
        return redirect('leaves:detail', pk=leave_request.id)
    
    try:
        # Ολοκλήρωση αίτησης
        leave_request.status = 'COMPLETED'
        leave_request.completed_at = timezone.now()
        # Ενημερώνουμε τα πεδία επεξεργασίας μόνο αν δεν έχουν ήδη θεσεί
        if not leave_request.processed_by:
            leave_request.processed_by = request.user
        if not leave_request.processed_at:
            leave_request.processed_at = timezone.now()
        leave_request.save()
        
        messages.success(request, 'Η αίτηση ολοκληρώθηκε επιτυχώς!')
        
    except Exception as e:
        messages.error(request, f'Σφάλμα κατά την ολοκλήρωση: {str(e)}')
    
    return redirect('leaves:detail', pk=leave_request.id)