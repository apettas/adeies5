import csv
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from leaves.models import LeaveType


class Command(BaseCommand):
    help = 'Εισαγωγή τύπων άδειας από CSV με αυτόματη συμπλήρωση κενών τιμών'

    BOOL_TRUE_VALUES = {'1', 'true', 'yes', 'y', 'ναι'}
    BOOL_FALSE_VALUES = {'0', 'false', 'no', 'n', 'οχι', 'όχι'}
    VALID_WORKFLOW_VARIANTS = {'STANDARD', 'KEDASY', 'SDEY'}

    FIELD_DEFAULTS = {
        'subject_text': None,
        'decision_text': None,
        'folder': 'Γενικός Φάκελος/',
        'instructions': '',
        'max_days': 30,
        'requires_approval': True,
        'is_active': True,
        'affects_regular_leave_balance': False,
        'is_simple': False,
        'workflow_variant': 'STANDARD',
        'is_sick_leave_yd': False,
        'is_sick_leave_total': False,
        'is_revocation': False,
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--csv',
            type=Path,
            default=Path(settings.BASE_DIR) / 'typoi5.csv',
            help='Διαδρομή αρχείου CSV. Προεπιλογή: BASE_DIR/typoi5.csv',
        )
        parser.add_argument(
            '--delimiter',
            default=';',
            help='Ο διαχωριστής του CSV. Προεπιλογή: ;',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Προεπισκόπηση εισαγωγής χωρίς εγγραφές στη βάση.',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Ενημέρωση υπαρχόντων τύπων άδειας με βάση το code.',
        )

    def handle(self, *args, **options):
        csv_path = options['csv']
        if not csv_path.is_absolute():
            csv_path = Path.cwd() / csv_path

        if not csv_path.exists():
            raise CommandError(f'Δεν βρέθηκε το αρχείο CSV: {csv_path}')

        rows = self._read_csv(csv_path, options['delimiter'])
        if not rows:
            raise CommandError('Το CSV δεν περιέχει δεδομένα.')

        self.stdout.write(f'Ανάγνωση CSV: {csv_path}')
        self.stdout.write(f'Εγγραφές: {len(rows)}')

        operations = []
        for row_number, row in enumerate(rows, start=2):
            operations.append(self._prepare_operation(row, row_number))

        created = updated = unchanged = skipped = 0
        with transaction.atomic():
            for operation in operations:
                if operation['error']:
                    skipped += 1
                    self.stdout.write(self.style.ERROR(f'Γραμμή {operation["row_number"]}: {operation["error"]}'))
                    continue

                if options['dry_run']:
                    action = 'Θα ενημερωθεί' if operation['exists'] else 'Θα δημιουργηθεί'
                    self.stdout.write(f'{action}: {operation["code"]} - {operation["data"]["name"]}')
                    continue

                if operation['exists']:
                    if options['force']:
                        leave_type = LeaveType.objects.get(code=operation['code'])
                        changed = any(
                            getattr(leave_type, field) != value
                            for field, value in operation['data'].items()
                        )
                        if changed:
                            LeaveType.objects.filter(code=operation['code']).update(**operation['data'])
                            updated += 1
                            self.stdout.write(f'Ενημερώθηκε: {operation["code"]} - {operation["data"]["name"]}')
                        else:
                            unchanged += 1
                            self.stdout.write(f'Ήδη ενημερωμένος: {operation["code"]} - {operation["data"]["name"]}')
                    else:
                        unchanged += 1
                        self.stdout.write(f'Υπάρχει ήδη: {operation["code"]} - {operation["data"]["name"]}')
                else:
                    LeaveType.objects.create(code=operation['code'], **operation['data'])
                    created += 1
                    self.stdout.write(f'Δημιουργήθηκε: {operation["code"]} - {operation["data"]["name"]}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('Dry run: δεν έγιναν αλλαγές στη βάση.'))
        else:
            self.stdout.write(self.style.SUCCESS('Η εισαγωγή τύπων άδειας ολοκληρώθηκε.'))

        summary = (
            f'Σύνοψη: δημιουργήθηκαν={created}, ενημερώθηκαν={updated}, '
            f'αμετάβλητοι={unchanged}, παραλείφθηκαν={skipped}'
        )
        self.stdout.write(summary)

    def _read_csv(self, csv_path, delimiter):
        with csv_path.open('r', encoding='utf-8-sig', newline='') as csv_file:
            return list(csv.DictReader(csv_file, delimiter=delimiter))

    def _prepare_operation(self, row, row_number):
        code = self._clean(row.get('code'))
        if not code:
            return {
                'row_number': row_number,
                'code': '',
                'data': {},
                'exists': False,
                'error': 'λείπει το code',
            }

        name = self._clean(row.get('name'))
        if not name:
            return {
                'row_number': row_number,
                'code': code,
                'data': {},
                'exists': LeaveType.objects.filter(code=code).exists(),
                'error': 'λείπει το name',
            }

        data = {
            'name': name,
            'subject_text': self._clean(row.get('subject_text')) or name,
            'decision_text': self._clean(row.get('decision_text')) or name,
            'folder': self._clean(row.get('folder')) or self.FIELD_DEFAULTS['folder'],
            'instructions': self._clean(row.get('instructions')) or self.FIELD_DEFAULTS['instructions'],
            'max_days': self._parse_positive_integer(row.get('max_days'), row_number, code),
            'requires_approval': self._parse_bool(
                row.get('requires_approval'),
                'requires_approval',
                self.FIELD_DEFAULTS['requires_approval'],
            ),
            'is_active': self._parse_bool(
                row.get('is_active'),
                'is_active',
                self.FIELD_DEFAULTS['is_active'],
            ),
            'affects_regular_leave_balance': self._parse_bool(
                row.get('affects_regular_leave_balance'),
                'affects_regular_leave_balance',
                self.FIELD_DEFAULTS['affects_regular_leave_balance'],
            ),
            'is_simple': self._parse_bool(
                row.get('is_simple'),
                'is_simple',
                self.FIELD_DEFAULTS['is_simple'],
            ),
            'workflow_variant': self._parse_workflow_variant(
                row.get('workflow_variant'),
                row_number,
                code,
            ),
            'is_sick_leave_yd': self._parse_bool(
                row.get('is_sick_leave_yd'),
                'is_sick_leave_yd',
                self.FIELD_DEFAULTS['is_sick_leave_yd'],
            ),
            'is_sick_leave_total': self._parse_bool(
                row.get('is_sick_leave_total'),
                'is_sick_leave_total',
                self.FIELD_DEFAULTS['is_sick_leave_total'],
            ),
            'is_revocation': self._parse_bool(
                row.get('is_revocation'),
                'is_revocation',
                self.FIELD_DEFAULTS['is_revocation'],
            ),
        }

        if isinstance(data['max_days'], dict):
            return {
                'row_number': row_number,
                'code': code,
                'data': data,
                'exists': LeaveType.objects.filter(code=code).exists(),
                'error': data['max_days']['error'],
            }

        if isinstance(data['workflow_variant'], dict):
            return {
                'row_number': row_number,
                'code': code,
                'data': data,
                'exists': LeaveType.objects.filter(code=code).exists(),
                'error': data['workflow_variant']['error'],
            }

        for field in ('requires_approval', 'is_active', 'affects_regular_leave_balance', 'is_simple',
                      'is_sick_leave_yd', 'is_sick_leave_total', 'is_revocation'):
            if isinstance(data[field], dict):
                return {
                    'row_number': row_number,
                    'code': code,
                    'data': data,
                    'exists': LeaveType.objects.filter(code=code).exists(),
                    'error': data[field]['error'],
                }

        return {
            'row_number': row_number,
            'code': code,
            'data': data,
            'exists': LeaveType.objects.filter(code=code).exists(),
            'error': None,
        }

    def _clean(self, value):
        if value is None:
            return ''
        return str(value).strip()

    def _parse_positive_integer(self, value, row_number, code):
        value = self._clean(value)
        if not value:
            return self.FIELD_DEFAULTS['max_days']

        try:
            parsed = int(value)
        except ValueError:
            return {'error': f'άκυρο max_days="{value}"'}

        if parsed < 0:
            return {'error': f'άκυρο max_days="{value}"'}

        return parsed

    def _parse_bool(self, value, field_name, default):
        value = self._clean(value)
        if not value:
            return default

        normalized = value.lower().strip()
        if normalized in self.BOOL_TRUE_VALUES:
            return True
        if normalized in self.BOOL_FALSE_VALUES:
            return False

        return {
            'error': f'άκυρο {field_name}="{value}"',
        }

    def _parse_workflow_variant(self, value, row_number, code):
        value = self._clean(value) or self.FIELD_DEFAULTS['workflow_variant']
        if value not in self.VALID_WORKFLOW_VARIANTS:
            return {'error': f'άκυρο workflow_variant="{value}"'}
        return value
