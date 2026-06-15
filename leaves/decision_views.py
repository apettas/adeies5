from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.contrib import messages
from django.urls import reverse
import os
from pathlib import Path
from datetime import datetime

from django.conf import settings

from leaves.models import LeaveRequest, Logo, Info, Ypopsin, Signee, Letterhead
from leaves.crypto_utils import SecureFileHandler
from leaves.decision_helpers import build_decision_pdf_filename


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
    
    if leave_request.status == 'IN_REVIEW':
        leave_request.start_decision_preparation(request.user)
    
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
    
    # Διάβασε το SVG εθνόσημου για ενσωμάτωση στο editor
    ethnosimo_svg_path = Path(settings.BASE_DIR) / 'static' / 'ethnosimo.svg'
    ethnosimo_svg_inline = ''
    if ethnosimo_svg_path.exists():
        with open(ethnosimo_svg_path, 'r', encoding='utf-8') as f:
            svg_content = f.read()
        svg_content = svg_content.replace('<svg', '<svg width="80px" style="margin-bottom:8px;"')
        ethnosimo_svg_inline = svg_content
    
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
        'ethnosimo_svg_inline': ethnosimo_svg_inline,
        'notification_recipients': leave_request.user.notification_recipients or '',
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
        
        # Επεξεργασμένα κείμενα - υποστήριξη νέου ενιαίου editor και παλαιών textareas
        edited_info_text = request.POST.get('info_text', '')
        edited_ypopsin_text = request.POST.get('ypopsin_text', '')
        edited_signee_text = request.POST.get('signee_text', '')
        edited_decision_body = request.POST.get('decision_body', '')
        full_decision_html = request.POST.get('full_decision_html', '')
        
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
        
        if leave_request.status == 'IN_REVIEW':
            leave_request.start_decision_preparation(request.user)
        leave_request.save()
        
        # Αν υπάρχει full_decision_html από τον WYSIWYG editor,
        # το χρησιμοποιούμε απευθείας ως ολόκληρο το περιεχόμενο του PDF
        # (wrap σε βασικό template με page size και CSS)
        if full_decision_html:
            html_string = f"""<!DOCTYPE html>
<html lang="el">
<head>
    <meta charset="UTF-8">
    <style>
        @page {{ size: A4; margin: 1.5cm; }}
        body {{ font-family: "DejaVu Sans", "Arial", sans-serif; font-size: 11pt; line-height: 1.4; color: #000; margin: 0; padding: 0; }}
        .ethnosimo {{ width: 80px; height: auto; margin-bottom: 8px; }}
        .apofasi-title {{ font-size: 22pt; font-weight: bold; text-transform: uppercase; letter-spacing: 4px; }}
        .section-divider {{ border: none; border-top: 1px solid #999; margin: 12px 0; }}
        .small-divider {{ border: none; border-top: 1px dotted #ccc; margin: 8px 0; }}
        .subject-label {{ font-weight: bold; font-size: 12pt; }}
        .subject-content {{ font-weight: bold; font-size: 12pt; margin-left: 5px; }}
        .ypopsin-content {{ font-size: 8.5pt; white-space: pre-line; line-height: 1.25; margin-top: 2px; }}
        .apofasizoume {{ font-weight: bold; text-align: center; font-size: 13pt; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 8px; }}
        .decision-body {{ font-size: 11pt; line-height: 1.4; text-align: justify; }}
        .signature-spacer {{ height: 35px; }}
        .signature-name {{ font-size: 11pt; font-weight: bold; }}
        .koinopoiisi-title {{ font-weight: bold; font-size: 11pt; margin-bottom: 5px; }}
        .koinopoiisi-content {{ font-size: 9pt; white-space: pre-line; }}
    </style>
</head>
<body>
    {full_decision_html}
</body>
</html>"""
        else:
            # Προετοιμασία context για PDF (παλαιός τρόπος με ατομικά πεδία)
            from leaves.models import Letterhead
            active_letterhead = Letterhead.get_active()
            
            user = leave_request.user
            name_accusative = user.name_accusative or ''
            
            ethnosimo_svg_path = Path(settings.BASE_DIR) / 'static' / 'ethnosimo.svg'
            ethnosimo_inline = ''
            if ethnosimo_svg_path.exists():
                with open(ethnosimo_svg_path, 'r', encoding='utf-8') as f:
                    svg_content = f.read()
                svg_content = svg_content.replace('<svg', '<svg width="80px" style="margin-bottom:8px;"')
                ethnosimo_inline = svg_content
            
            context = {
                'leave_request': leave_request,
                'logo': logo,
                'info_text': edited_info_text or (info.info if info else ''),
                'ypopsin_text': edited_ypopsin_text or (ypopsin.ypopsin if ypopsin else ''),
                'signee_text': edited_signee_text or (signee.signee if signee else ''),
                'signee_name': signee.signee_name if signee else '',
                'signee_title': signee.signee if signee else '',
                'current_date': timezone.now().strftime('%d/%m/%Y'),
                'subject_text': leave_request.leave_type.subject_text or '',
                'decision_text': leave_request.leave_type.decision_text or '',
                'employee_gender': user.gender or 'MALE',
                'employee_name_accusative': name_accusative,
                'employee_role': user.role_description or '',
                'notification_recipients': user.notification_recipients or '',
                'ethnosimo_inline': ethnosimo_inline,
                'letterhead': active_letterhead,
                'decision_body': edited_decision_body,
            }
            
            html_string = render_to_string('leaves/decision_pdf_template.html', context)
        
        # Δημιουργία PDF
        html = HTML(string=html_string)
        pdf_content = html.write_pdf()
        
        filename = build_decision_pdf_filename(leave_request)

        # Δημιουργία directory αν δεν υπάρχει
        pdf_dir = os.path.join('media', 'private_media', 'leave_decisions', str(leave_request.id))
        os.makedirs(pdf_dir, exist_ok=True)

        # Κρυπτογράφηση και αποθήκευση με τη νέα μέθοδο
        pdf_path = os.path.join(pdf_dir, filename)
        handler = SecureFileHandler()
        encrypted_path, encryption_key = handler.save_encrypted_bytes(pdf_content, pdf_path)
        
        # Έλεγχος αν είναι preview ή finalize
        action = request.POST.get('action', 'finalize')
        
        if action == 'preview':
            # Μόνο προεπισκόπηση: επιστρέφουμε PDF χωρίς αποθήκευση
            response = HttpResponse(pdf_content, content_type='application/pdf')
            response['Content-Disposition'] = content_disposition_header(
                as_attachment=False, filename=filename
            )
            return response
        
        # Ενημέρωση των πεδίων PDF (finalize)
        leave_request.decision_pdf_path = encrypted_path
        leave_request.decision_pdf_encryption_key = encryption_key
        leave_request.decision_pdf_size = len(pdf_content)
        # Μόνο αν είμαστε σε DECISION_PREPARATION, προχωράμε σε PENDING_SIGNATURES
        # Αν είμαστε ήδη σε PENDING_SIGNATURES (αναγέννηση PDF), δεν αλλάζουμε status
        if leave_request.status == 'DECISION_PREPARATION':
            leave_request.send_to_signatures(request.user)
            messages.success(request, 'Η απόφαση PDF δημιουργήθηκε και η αίτηση προωθήθηκε προς υπογραφές.')
        else:
            leave_request.save()
            messages.success(request, 'Η απόφαση PDF αναγεννήθηκε επιτυχώς.')
        
        # Επιστροφή PDF στον χρήστη
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = content_disposition_header(
            as_attachment=True, filename=filename
        )
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
        
        filename = build_decision_pdf_filename(leave_request)

        # Δημιουργία response
        response = HttpResponse(pdf_content, content_type='application/pdf')
        response['Content-Disposition'] = content_disposition_header(
            as_attachment=is_download, filename=filename
        )
        
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
        if leave_request.finalize_with_exact_copy(request.user):
            # Ενημέρωση total_sick_leave_last_5_years (5ετία) – το sick_days_current_year
            # ήδη ενημερώνεται μέσα στο finalize_with_exact_copy() → _update_leave_balance_on_completion()
            if leave_request.leave_type.is_sick_leave_total:
                from leaves.models import YearlySickLeaveTotal
                from django.db.models import Sum
                current_year = timezone.now().year
                user = leave_request.user
                user.refresh_from_db(fields=['sick_days_current_year'])
                five_years_ago = current_year - 5
                last_5 = YearlySickLeaveTotal.objects.filter(
                    employee=user, year__gte=five_years_ago, year__lte=current_year
                ).aggregate(total=Sum('total_days'))['total'] or 0
                user.total_sick_leave_last_5_years = last_5
                user.save(update_fields=['total_sick_leave_last_5_years'])
            
            messages.success(request, 'Η αίτηση ολοκληρώθηκε επιτυχώς!')
        else:
            messages.error(request, 'Δεν ήταν δυνατή η ολοκλήρωση της αίτησης.')
    except Exception as e:
        messages.error(request, f'Σφάλμα κατά την ολοκλήρωση: {str(e)}')
    
    return redirect('leaves:detail', pk=leave_request.id)


@login_required
def send_to_signatures_view(request, pk):
    """DECISION_PREPARATION → PENDING_SIGNATURES όταν υπάρχει ήδη PDF απόφασης"""
    if not request.user.is_leave_handler:
        messages.error(request, 'Δεν έχετε δικαίωμα πρόσβασης σε αυτή τη σελίδα.')
        return redirect('leaves:dashboard_redirect')
    
    leave_request = get_object_or_404(LeaveRequest, pk=pk)
    
    if not leave_request.has_decision_pdf():
        messages.error(request, 'Απαιτείται PDF απόφασης πριν την αποστολή προς υπογραφές.')
        return redirect('leaves:prepare_decision_preview', leave_request_id=leave_request.id)
    
    if leave_request.send_to_signatures(request.user):
        messages.success(request, 'Η αίτηση προωθήθηκε προς υπογραφές.')
    else:
        messages.error(request, 'Δεν ήταν δυνατή η προώθηση προς υπογραφές.')
    
    return redirect('leaves:leave_request_detail', pk=leave_request.id)