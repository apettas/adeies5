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
        'django_cas_ng.backends.CASBackend',
    )

    CAS_VERSION = '3'
    CAS_CREATE_USER = True
    CAS_LOGOUT_COMPLETELY = True
    CAS_REDIRECT_URL = '/'
    CAS_RETRY_LOGIN = False
    CAS_APPLY_ATTRIBUTES_TO_USER = True
    CAS_USERNAME_ATTRIBUTE = 'email'

    # HTTPS service URL — απαιτείται από το ΠΣΔ (καταχωρημένο service με https)
    CAS_FORCE_SSL_SERVICE_URL = config('CAS_FORCE_SSL_SERVICE_URL', default=True, cast=bool)
    # Βάση URL πίσω από reverse proxy (π.χ. https://sadeies.pdede.gov.gr)
    CAS_ROOT_PROXIED_AS = config('CAS_ROOT_PROXIED_AS', default='').rstrip('/')

    # Proxy-granting ticket (δεν χρειάζεται για την περίπτωσή μας)
    CAS_PROXY_CALLBACK = None

    # Χαρτογράφηση CAS attributes → Django User fields
    # Το ΠΣΔ στέλνει: email, givenName, sn, gsnfathername, employeeNumber,
    # gsnBranch, title, ou, umdobject, businessCategory
    CAS_USER_ATTRIBUTES_MAPPING = {
        'email': 'email',
        'first_name': 'givenName',
        'last_name': 'sn',
        'father_name': 'gsnfathername',
        'role_description': 'title',
        'employee_number': 'employeeNumber',
    }

    # Session timeout: 8 ώρες (480 λεπτά) όπως δηλώνεται στο helpdesk
    SESSION_COOKIE_AGE = 28800  # 8 ώρες σε δευτερόλεπτα
    SESSION_SAVE_EVERY_REQUEST = True
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True
