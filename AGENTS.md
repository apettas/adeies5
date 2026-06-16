# pdede_leaves — ΠΔΕΔΕ Σύστημα Διαχείρισης Αδειών

Greek Regional Directorate of Education (ΠΔΕΔΕ) leave management system. Handles employee leave requests through a multi-level approval workflow, generates PDF decisions, manages encrypted secure documents, and tracks leave balances with a full audit-ledger.

## Tech Stack

- **Backend**: Python 3, Django 5.2, Gunicorn
- **Database**: PostgreSQL 15 (alpine)
- **Frontend**: Bootstrap 5, django-bootstrap5, django-crispy-forms (crispy-bootstrap5), HTMX
- **PDF**: WeasyPrint (decision/PDF generation)
- **Encryption**: PyCryptodome (AES-256 for secure file attachments)
- **Cache/Queue**: Redis, django-redis, Celery
- **Static/Media**: WhiteNoise, Nginx (production)
- **Infrastructure**: Docker Compose (db, redis, web, nginx services)
- **Config**: python-decouple (`.env` file)

## Architecture

### Django Apps

| App | Purpose |
|-----|---------|
| `accounts` | Custom User model, Department hierarchy, Roles, Registration workflow |
| `leaves` | LeaveRequest state machine, LeaveTypes, Periods, SecureFiles, Decisions, PDFs, Balance ledger |
| `notifications` | In-app notifications via GenericForeignKey to any model |

### Key Model: `accounts.User` (custom, email-as-username)

- `USERNAME_FIELD = 'email'` — username is removed
- Fields: `first_name`, `last_name`, `email`, `department` (FK), `roles` (M2M), `employee_type` (FK), `specialty`, `gender`, `father_name`, `phone1`
- Category: `employee_type` (ADMINISTRATIVE / EDUCATIONAL / SUBSTITUTE / SDEU_SUPPORT / EDUCATION_DIRECTOR / OTHER)
- Registration: `registration_status` (PENDING / APPROVED / REJECTED), `approved_by`, `approval_date`
- Leave balances: `annual_leave_entitlement`, `current_regular_leave_balance` (ledger cache), `sick_leave_with_declaration`, `sick_days_current_year`, `total_sick_leave_last_5_years`
- Permissions: `can_request_leave`

### Roles & Permissions (`accounts.Role` + M2M)

Canonical role codes (see `accounts/role_constants.py`):

| Code | Property | Σκοπός |
|------|----------|--------|
| `EMPLOYEE` | `is_employee` | Υποβολή αιτήσεων |
| `MANAGER` | `is_department_manager` | UI/δικαιώματα προϊσταμένου |
| `LEAVE_HANDLER` | `is_leave_handler` | Επεξεργασία αιτήσεων ΠΔΕΔΕ |
| `SECRETARY` | `is_secretary` | Γραμματεία / πρωτόκολλο ΚΕΔΑΣΥ |
| `ADMIN` | `is_administrator` | Διαχείριση εφαρμογής αδειών |
| `HR_ADMIN`, `HR_OFFICER` | — | HR / βασικά δεδομένα |

**Διαχωρισμός ρόλων vs Django auth:**

- `is_superuser` → πλήρης πρόσβαση (συμπεριλαμβανομένου `is_administrator`)
- `is_staff` → μόνο Django admin panel, όχι εφαρμογία αδειών
- `ADMIN` role → διαχείριση ρόλων/χρηστών στην εφαρμογή (χωρίς υποχρεωτικά superuser)

**Προϊστάμενος τμήματος — δύο έννοιες:**

1. **`Department.manager` (FK)** — *authoritative* για ιεραρχία εγκρίσεων (`get_approving_manager`, `is_manager_of_department`, `get_subordinates`). Όταν οριστεί, signal προσθέτει αυτόματα ρόλο `MANAGER`.
2. **Ρόλος `MANAGER`** — δικαίωμα χρήσης manager dashboard και έγκρισης (αν είναι και ο σωστός `get_approving_manager()`).

`User._role_codes()` χρησιμοποιεί prefetched roles όταν το queryset έχει `.prefetch_related('roles')`.

### Key Model: `accounts.Department`

- Hierarchical via `parent_department` (self-referential FK)
- Typed via `DepartmentType` (code: AUTOTELOUS, PDEDE_MAIN, KEDASY, KEPEA, SDEY, PEDAGOGICAL, etc.)
- Linked to `Prefecture` (νομός) and `Headquarters` (έδρα)
- **`manager` FK to User** — επίσημος προϊστάμενος τμήματος (authoritative για ιεραρχία)

### Key Model: `leaves.LeaveRequest` — 11-status state machine

```
DRAFT → SUBMITTED → PENDING_PROTOCOL → IN_REVIEW → COMPLETED
                   ↘ SUPERVISOR_REJECTED
                   ↘ CANCELLED_BY_APPLICANT
                                    ↘ WAITING_FOR_DOCUMENTS → IN_REVIEW
                                    ↘ REJECTED_BY_LEAVES_DEPT
```

- Multiple `LeavePeriod` objects per request (start_date / end_date)
- Protocol tracking: `kedasy_kepea_protocol_number`, `pdede_protocol_number`
- Decision PDF fields: `decision_pdf_path`, `decision_pdf_encryption_key`, `decision_logo`, `decision_info`, `decision_ypopsin`, `decision_signee`, `final_decision_text`
- Exact copy (ΣΗΔΕ ακριβές αντίγραφο): `exact_copy_pdf_path`, `exact_copy_uploaded_by`
- Locking: `locking_user`, `locked_at` (30-minute timeout)
- Audit: `LeaveActionLog`, `LeaveAccessLog`

### Workflow Variants

`LeaveType.workflow_variant` controls the approval path:
- `STANDARD` — default
- `KEDASY` — KEDASY-specific routing
- `SDEY` — SDEY-specific routing

Defined in `WorkflowVariant`, `ApprovalRule`, `RequiredAttachmentRule`, `DecisionTemplate`.

### Approval Hierarchy Logic (`User.get_approving_manager`)

1. Αν ο χρήστης είναι **FK manager** του τμήματός του (`is_manager_of_department`) → εγκρίνει ο γονικού ή PDEDE
2. Αν όχι → εγκρίνει ο `Department.manager` (ανέβασμα ιεραρχίας)
3. Fallback: χρήστης με ρόλο `MANAGER` στο τμήμα (μόνο αν λείπει FK)
4. `_find_pdede_manager()` → PDEDE_MAIN manager

## Code Style

### Python

- Greek docstrings and inline comments
- `verbose_name` / `verbose_name_plural` in Greek on every model field
- Class names: PascalCase (`UserManager`, `LeaveRequestForm`, `ManagerDashboardView`)
- Functions/methods: snake_case (`get_approving_manager`, `update_leave_balance`)
- Views: mix of Class-Based Views (ListView, CreateView, DetailView) with LoginRequiredMixin + functional views with `@login_required`
- Imports: standard library → Django → third-party → project apps, sections separated by blank line
- F-strings preferred for formatting

### Django Conventions

- Custom User model: `AUTH_USER_MODEL = 'accounts.User'`
- URL namespacing: `app_name = 'leaves'` with `reverse('leaves:employee_dashboard')`
- Manager pattern: `UserManager(BaseUserManager)` with `create_user` / `create_superuser`
- Form validation: `clean_<field>()` + `clean()` with `ValidationError`
- Messages: `django.contrib.messages` with Greek strings
- Querysets: favor `select_related` for FK relationships; `prefetch_related('roles')` σε λίστες χρηστών
- GenericRelation: `LeaveRequest.notifications = GenericRelation(Notification)`

### HTML Templates

- Location: `templates/` directory at project root, organized by app (`templates/accounts/`, `templates/leaves/`, `templates/notifications/`)
- Bootstrap 5 classes, django-bootstrap5 template tags
- HTMX via `django-htmx` (middleware, template tags)
- Template structure: `base.html` → app-specific templates → `includes/` for partials

## Development Workflow

### Setup (first time)

```bash
make dev-setup
# Builds Docker images, starts services, runs migrations, collects static files
```

### Daily commands

```bash
make up          # docker-compose up -d
make down        # docker-compose down
make logs        # docker-compose logs -f
make shell       # python manage.py shell
make bash        # bash in web container
make migrate     # runs fix_migrations.py
make test        # python manage.py test
make createsuperuser
```

### Environment Variables (.env)

```env
SECRET_KEY=...
DEBUG=True
DB_NAME=pdede_leaves
DB_USER=pdede_user
DB_PASSWORD=pdede_password
DB_HOST=db
DB_PORT=5432
ALLOWED_HOSTS=localhost,127.0.0.1
```

## Database & Migrations

- PostgreSQL with Greek collation (`el_GR.UTF-8`)
- All Django migrations in `accounts/migrations/` and `leaves/migrations/`
- Run migrations via `make migrate` or `docker-compose exec web python manage.py migrate`
- Migration fixes: `make fix-migrations` runs `fix_migrations.py`
- Backup: `make backup` (pg_dump), `make restore` (psql restore)
- Default primary key: `BigAutoField`

## Testing

### Framework
- Django TestCase with `TestDataMixin` for reusable test data setup
- Test files in `accounts/tests/` and `leaves/tests/`
- Root-level test scripts: `run_tests.py`, `test_leave_balance_deduction.py`, `test_pdf_generation.py`, `test_real_leave_process.py`, `test_sdei_kedasy_simple.py`

### Pattern
```python
class MyTests(TestDataMixin, TestCase):
    def setUp(self):
        super().setUp()
        # Additional setup
        self.client = Client()
        self.client.force_login(self.some_user)
    
    def test_something(self):
        response = self.client.post(reverse('leaves:some_url'), data)
        self.assertEqual(response.status_code, 302)
        # Assert state changes
```

### Running
```bash
make test                          # all tests
docker-compose exec web python manage.py test accounts.tests
docker-compose exec web python manage.py test leaves.tests.test_integration
```

## Security

- **Encryption**: SecureFile attachments encrypted with AES-256 (PyCryptodome), keys stored as hex in DB
- **Environment variables**: All secrets via python-decouple, never hardcoded
- **File storage**: `private_media/` for encrypted files, `media/` for public files
- **GDPR logging**: `LeaveAccessLog` tracks who views/downloads which leave request
- **Authentication**: Email-based login, registration requires approval workflow
- **CSRF**: Django middleware active (except where explicitly exempted)
- **Permission checks**: `can_user_view()`, `can_add_kedasy_kepea_protocol()`, `has_leave_request_permission()` on every protected action
- **Locking**: Leave requests lockable by handlers with 30-minute timeout

## Key Patterns

### Registration Workflow
1. User registers → `registration_status='PENDING'`, `is_active=False`
2. Admin/Manager approves via `User.approve_registration()` → status 'APPROVED', `is_active=True`
3. User can now log in and submit leave requests

### Leave Request Lifecycle
1. Employee creates DRAFT, optionally edits, then submits
2. Manager approves (status → PENDING_PROTOCOL) or rejects
3. Handler processes: adds protocol, requests documents, or rejects
4. Handler generates decision PDF (with WeasyPrint), uploads exact copy from ΣΗΔΕ
5. Request completed → leave balance deducted

### Balance Ledger (Append-Only)
- `RegularLeaveBalanceEntry` records every balance-affecting event
- `create_balance_entry()` in `leaves/utils/balance_ledger.py` creates entry + updates cached field
- `get_last_balance()` reads the source-of-truth from the last entry
- Corrections are **new entries**, never edits (is_locked=True)

### Notification System
- `notifications.utils.create_notification(user, title, message, type, related_object)`
- GenericForeignKey links notifications to any model
- Mark as read, get unread count, delete old notifications

### Decision PDF Generation
1. `prepare_decision_preview()` — renders preview with Letterhead, Logo, Info, Ypopsin, Signee
2. `generate_final_decision_pdf()` — generates encrypted PDF via WeasyPrint
3. Decision PDF stored in `media/private_media/leave_decisions/{request_id}/`
4. Exact copy uploaded by handler after ΣΗΔΕ signatures

## Common Tasks

### Adding a new LeaveType
```python
LeaveType.objects.create(
    code='NEW_TYPE',
    name='Νέος Τύπος',
    requires_approval=True,
    counts_against_balance=True,
    max_days=30,
    workflow_variant='STANDARD'
)
```

### Adding a new management command
- File: `accounts/management/commands/<name>.py` or `leaves/management/commands/<name>.py`
- Class: `class Command(BaseCommand)` with `help`, `add_arguments`, `handle`

### Adding a new migration
```bash
docker-compose exec web python manage.py makemigrations <app_name>
docker-compose exec web python manage.py migrate
```

### Creating test users
```bash
docker-compose exec web python manage.py create_test_users
```
Or use the management commands in `accounts/management/commands/`.

## File Organization

```
adeies5/
├── AGENTS.md                   # This file
├── Dockerfile / Dockerfile.prod
├── Makefile
├── docker-compose.yml / .prod.yml
├── manage.py
├── requirements.txt
├── pdede_leaves/               # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/                   # Users, departments, roles
│   ├── models.py, views.py, forms.py, admin.py, urls.py
│   ├── management/commands/    # Custom management commands
│   ├── migrations/
│   └── tests/
├── leaves/                     # Core leave management
│   ├── models.py, views.py, forms.py, admin.py, urls.py
│   ├── decision_views.py, decision_helpers.py
│   ├── calendar_views.py, balance_views.py
│   ├── crypto_utils.py, attachment_helpers.py, dashboard_utils.py
│   ├── utils/
│   │   ├── balance_ledger.py
│   │   └── working_days.py
│   ├── management/commands/
│   ├── migrations/
│   └── tests/
├── notifications/              # In-app notifications
│   ├── models.py, views.py, urls.py, admin.py
│   └── utils.py
├── templates/                  # HTML templates
│   ├── base.html
│   ├── accounts/, leaves/, notifications/
├── static/                     # Custom static files
├── staticfiles/                # Collected static (admin + django_htmx)
├── media/                      # Public media (leave_decisions for PDFs)
└── private_media/              # Encrypted leave request attachments
```