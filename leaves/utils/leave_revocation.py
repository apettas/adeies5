"""Βοηθητικά για ανάκληση ολοκληρωμένης άδειας (όχι ανάκληση αίτησης)."""
from leaves.models import LeaveType


REVOCATION_TYPE_CODE = 'LT_REVOCATION'


def get_or_create_revocation_leave_type():
    """Ενεργός τύπος άδειας ανάκλησης (εσωτερικός — όχι στο dropdown νέας αίτησης)."""
    leave_type = LeaveType.objects.filter(is_revocation=True, is_active=True).order_by('pk').first()
    if leave_type:
        return leave_type

    leave_type, _ = LeaveType.objects.get_or_create(
        code=REVOCATION_TYPE_CODE,
        defaults={
            'name': 'Ανάκληση Άδειας',
            'requires_approval': True,
            'is_active': True,
            'is_revocation': True,
            'affects_regular_leave_balance': False,
            'is_simple': False,
            'subject_text': 'Ανάκληση Άδειας',
            'decision_text': 'ανάκληση της κατωτέρω άδειας',
            'instructions': (
                'Η αίτηση ανάκλησης δημιουργείται μόνο από ολοκληρωμένη άδεια '
                '(κουμπί «Ανάκληση άδειας»).'
            ),
        },
    )
    if not leave_type.is_revocation or not leave_type.is_active:
        leave_type.is_revocation = True
        leave_type.is_active = True
        leave_type.affects_regular_leave_balance = False
        leave_type.save(update_fields=[
            'is_revocation', 'is_active', 'affects_regular_leave_balance',
        ])
    return leave_type


def build_revocation_request_body_text(parent_leave, scope, days):
    """Προεπιλεγμένο κείμενο σώματος PDF για αίτηση ανάκλησης."""
    scope_label = 'ολική' if scope == 'TOTAL' else 'μερική'
    protocol = parent_leave.pdede_protocol_number or parent_leave.protocol_number or '—'
    protocol_date = ''
    if parent_leave.pdede_protocol_date:
        protocol_date = parent_leave.pdede_protocol_date.strftime('%d/%m/%Y')
    elif parent_leave.completed_at:
        protocol_date = parent_leave.completed_at.strftime('%d/%m/%Y')

    periods = list(parent_leave.periods.all().order_by('start_date'))
    if periods:
        period_bits = ', '.join(
            f'{p.start_date.strftime("%d/%m/%Y")}–{p.end_date.strftime("%d/%m/%Y")}'
            for p in periods
        )
    else:
        period_bits = '—'

    return (
        f'Παρακαλώ να μου χορηγήσετε {scope_label} ανάκληση της άδειας '
        f'«{parent_leave.leave_type.name}» (αίτηση #{parent_leave.id}), '
        f'αρ. πρωτ. ΠΔΕΔΕ {protocol}'
        + (f' / {protocol_date}' if protocol_date else '')
        + f', αρχικά διαστήματα: {period_bits}, '
        f'για τις κάτωθι ημερομηνίες (ημέρες ανάκλησης: {days}):'
    )
