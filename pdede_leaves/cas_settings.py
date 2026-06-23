"""
CAS (Central Authentication Service) settings for Σχολικό Δίκτυο (sch.gr).
Ενεργοποιείται μόνο όταν οριστεί η μεταβλητή CAS_SERVER_URL στο .env.
"""
from decouple import config

CAS_SERVER_URL = config('CAS_SERVER_URL', default='')
CAS_ENABLED = bool(CAS_SERVER_URL)

if CAS_ENABLED:
    AUTHENTICATION_BACKENDS = (
        'django.contrib.auth.backends.ModelBackend',
        'accounts.cas_backend.PdedeCASBackend',
    )

    CAS_VERSION = '3'
    CAS_CREATE_USER = True
    CAS_LOGOUT_COMPLETELY = True
    CAS_REDIRECT_URL = '/login/'
    CAS_LOGIN_NEXT_PAGE = '/login/'
    CAS_STORE_NEXT = True
    CAS_RETRY_LOGIN = False
    CAS_APPLY_ATTRIBUTES_TO_USER = True
    CAS_USERNAME_ATTRIBUTE = 'email'

    # Test SSO server — απενεργοποίηση SSL verify αν χρειάζεται
    CAS_VERIFY_SSL_CERTIFICATE = config(
        'CAS_VERIFY_SSL_CERTIFICATE',
        default='sso-01-test' not in CAS_SERVER_URL,
        cast=bool,
    )

    # HTTPS service URL — απαιτείται από το ΠΣΔ (καταχωρημένο service με https)
    CAS_FORCE_SSL_SERVICE_URL = config('CAS_FORCE_SSL_SERVICE_URL', default=True, cast=bool)
    # Βάση URL πίσω από reverse proxy (π.χ. https://sadeies.pdede.gov.gr)
    CAS_ROOT_PROXIED_AS = config('CAS_ROOT_PROXIED_AS', default='').rstrip('/')

    # Proxy-granting ticket (δεν χρειάζεται για την περίπτωσή μας)
    CAS_PROXY_CALLBACK = None

    # Μετονομασία CAS attributes → πεδία User πριν την εφαρμογή
    CAS_RENAME_ATTRIBUTES = {
        'givenName': 'first_name',
        'sn': 'last_name',
        'gsnfathername': 'father_name',
        'employeeNumber': 'employee_number',
        'gsnBranch': 'gsn_branch',
        'title': 'role_description',
        'Title': 'role_description',
        'ou': 'sso_organizational_unit',
        'mail': 'email',
    }

    # Session timeout: 8 ώρες (480 λεπτά) όπως δηλώνεται στο helpdesk
    SESSION_COOKIE_AGE = 28800  # 8 ώρες σε δευτερόλεπτα
    SESSION_SAVE_EVERY_REQUEST = True
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True
