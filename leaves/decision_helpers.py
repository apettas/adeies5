import base64
import re
from pathlib import Path

from django.conf import settings
from django.utils import timezone


DECISION_PDF_CSS = """
@page { size: A4; margin: 0.4cm; }
body {
    font-family: "DejaVu Sans", "Arial", sans-serif;
    font-size: 10pt;
    line-height: 1.2;
    color: #000;
    margin: 0;
    padding: 0;
}
.doc-top-spacer { height: 4.8em; }
.layout-table { width: 100%; border-collapse: collapse; border: none; table-layout: fixed; }
.layout-table td { border: none; vertical-align: top; padding: 0; }
.col-half { width: 50%; }
.header-left { text-align: center; padding-right: 6px; }
.header-right { text-align: center; padding-left: 6px; }
.ethnosimo-wrap { text-align: center; margin-bottom: 4px; line-height: 0; }
.ethnosimo {
    width: 60px;
    height: auto;
    display: inline-block;
    margin: 0;
    padding: 0;
    vertical-align: top;
}
.logo-text {
    font-size: 8pt;
    font-weight: bold;
    white-space: pre-line;
    line-height: 1.15;
    text-align: center;
    margin: 4px 0 6px;
}
.info-text {
    font-size: 9pt;
    font-weight: normal;
    white-space: pre-line;
    line-height: 1.15;
    text-align: left;
}
.section-divider {
    border: none;
    border-top: 1px solid #666;
    margin: 6px 0;
}
.apofasi-spacer { height: 13em; }
.apofasi-title {
    font-size: 16pt;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.45em;
    text-align: center;
    text-indent: 0.45em;
}
.subject-line { font-weight: bold; font-size: 10pt; text-align: left; margin: 0; }
.blank-line { height: 1.2em; }
.ypopsin-label { font-weight: bold; font-size: 11pt; text-align: left; margin: 0; }
.ypopsin-content {
    font-size: 9pt;
    font-weight: normal;
    white-space: pre-line;
    line-height: 1.2;
    text-align: left;
    margin: 0;
}
.apofasizoume {
    font-weight: bold;
    text-align: center;
    font-size: 12pt;
    letter-spacing: 2px;
    margin: 0;
}
.decision-body {
    font-size: 10pt;
    line-height: 1.25;
    text-align: justify;
    margin: 0;
}
.spacer-3 { height: 3.6em; }
.footer-left { text-align: center; padding-right: 8px; }
.footer-right { text-align: center; padding-left: 8px; }
.footer-spacer-3 { height: 3.6em; }
.footer-spacer-2 { height: 2.4em; }
.koinopoiisi-title {
    font-weight: bold;
    font-size: 10pt;
    text-align: left;
    margin: 0 0 4px;
}
.koinopoiisi-content {
    font-size: 9pt;
    font-weight: normal;
    white-space: pre-line;
    line-height: 1.15;
    text-align: left;
}
.signee-text {
    font-size: 10pt;
    font-weight: bold;
    white-space: pre-line;
    line-height: 1.15;
    text-align: center;
}
"""


def get_gender_dative_article(gender):
    """στο(ν) / στη(ν) όπως στο παλιό Access template."""
    if gender == 'FEMALE':
        return 'στη(ν)'
    if gender == 'MALE':
        return 'στο(ν)'
    return 'στο(ν)/στη(ν)'


def get_ethnosimo_markup(base_dir=None):
    """Επιστρέφει HTML εθνόσημου (PNG base64 ή inline SVG) για PDF/preview."""
    base = Path(base_dir or settings.BASE_DIR)
    static_dir = base / 'static'
    for filename in ('ethnosimo.png', 'ethnosimo.svg'):
        path = static_dir / filename
        if not path.exists():
            continue
        if filename.endswith('.png'):
            encoded = base64.b64encode(path.read_bytes()).decode('ascii')
            return (
                f'<div class="ethnosimo-wrap">'
                f'<img src="data:image/png;base64,{encoded}" class="ethnosimo" alt="Εθνόσημο">'
                f'</div>'
            )
        svg_content = path.read_text(encoding='utf-8')
        svg_content = svg_content.replace('<svg', '<svg class="ethnosimo" width="60"')
        return f'<div class="ethnosimo-wrap">{svg_content}</div>'
    return ''


def format_decision_days_phrase(days):
    """Φράση ημερών όπως στο επίσημο δείγμα: μίας (1) εργάσιμης ημέρας."""
    if not days:
        return ''
    if days == 1:
        return 'μίας (1) εργάσιμης ημέρας'
    if days == 2:
        return 'δύο (2) εργάσιμες ημέρες'
    if days == 3:
        return 'τριών (3) εργάσιμων ημερών'
    if days == 4:
        return 'τεσσάρων (4) εργάσιμων ημερών'
    if days == 5:
        return 'πέντε (5) εργάσιμες ημέρες'
    return f'{days} ({days}) εργάσιμες ημέρες'


def format_decision_dates_compact(leave_request):
    """Συμπαγείς ημερομηνίες ανά διάστημα άδειας."""
    periods = list(leave_request.periods.all().order_by('start_date'))
    if not periods:
        return ''

    def fmt(d):
        return f'{d.day}-{d.month}-{d.year}'

    def format_period(p):
        if p.days == 1:
            return f'στις {fmt(p.start_date)}'
        return f'από {fmt(p.start_date)} έως και {fmt(p.end_date)}'

    if len(periods) == 1:
        return format_period(periods[0])

    if all(p.days == 1 for p in periods):
        dates = [fmt(p.start_date) for p in periods]
        if len(dates) == 2:
            return f'στις {dates[0]} και {dates[1]}'
        return 'στις ' + ', '.join(dates[:-1]) + f' και {dates[-1]}'

    parts = [format_period(p) for p in periods]
    if len(parts) == 2:
        return f'{parts[0]} και {parts[1]}'
    return ', '.join(parts[:-1]) + f' και {parts[-1]}'


def build_decision_body_html(leave_request):
    """
    Κείμενο σώματος απόφασης (Access formula + επίσημο δείγμα):
    Χορηγούμε στο(ν)/στη(ν) <όνομα>, <ρόλος>, <κείμενο> <ημέρες> <ημερομηνίες>.
    """
    user = leave_request.user
    name = (user.name_accusative or user.full_name or '').strip()
    article = get_gender_dative_article(user.gender)
    role = (user.role_description or '').strip()
    decision_text = (leave_request.leave_type.decision_text or '').strip()
    days_phrase = format_decision_days_phrase(leave_request.total_days)
    dates_phrase = format_decision_dates_compact(leave_request)

    parts = [f'Χορηγούμε {article}']
    if name:
        parts.append(f'<b>{name}</b>,')
    if role:
        parts.append(f'{role},')
    if decision_text:
        parts.append(decision_text)
    if days_phrase:
        parts.append(f'{days_phrase},')
    if dates_phrase:
        parts.append(dates_phrase)

    return ' '.join(parts) + '.'


def build_decision_pdf_context(
    leave_request,
    logo=None,
    info=None,
    ypopsin=None,
    signee=None,
    edited_info_text='',
    edited_ypopsin_text='',
    edited_signee_text='',
    edited_decision_body='',
):
    """Context για το decision_pdf_template.html."""
    user = leave_request.user
    return {
        'leave_request': leave_request,
        'logo': logo,
        'info_text': edited_info_text or (info.info if info else ''),
        'ypopsin_text': edited_ypopsin_text or (ypopsin.ypopsin if ypopsin else ''),
        'signee_text': edited_signee_text or (signee.signee if signee else ''),
        'signee_title': signee.signee if signee else '',
        'subject_text': leave_request.leave_type.subject_text or '',
        'notification_recipients': user.notification_recipients or '',
        'ethnosimo_markup': get_ethnosimo_markup(),
        'decision_body': edited_decision_body or build_decision_body_html(leave_request),
        'decision_pdf_css': DECISION_PDF_CSS,
    }


def build_decision_pdf_filename(leave_request, reference_date=None):
    """
    Όνομα αρχείου απόφασης: yyyymmdd_Username_leavetype_Αποφαση.pdf
    Username = τοπικό μέρος email (πριν το @).
    leavetype = κωδικός τύπου άδειας ή το όνομά του.
    """
    ref = reference_date or leave_request.decision_created_at or timezone.now()
    date_str = ref.strftime('%Y%m%d')

    user = leave_request.user
    username = (user.email.split('@')[0] if user.email else 'user').strip()
    username = re.sub(r'[^\w\-]', '', username, flags=re.UNICODE) or 'user'

    leave_type = leave_request.leave_type
    lt = (leave_type.code or leave_type.name).strip()
    lt = re.sub(r'[\s/\\]+', '_', lt)
    lt = re.sub(r'[^\w\-]', '', lt, flags=re.UNICODE) or 'adidia'

    return f'{date_str}_{username}_{lt}_Αποφαση.pdf'
