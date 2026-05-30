"""
CAS (Central Authentication Service) settings for Σχολικό Δίκτυο (sch.gr).
Ενεργοποιείται μόνο όταν οριστεί η μεταβλητή CAS_SERVER_URL στο .env.
"""
from decouple import config

CAS_SERVER_URL = config('CAS_SERVER_URL', default='')
CAS_ENABLED = bool(CAS_SERVER_URL)

if CAS_ENABLED:
    CAS_VERSION = '3'
    CAS_CREATE_USER = False  # Θα κάνουμε auto-create/login στο callback
    CAS_LOGOUT_COMPLETELY = True
    CAS_REDIRECT_URL = '/'  # Μετά από logout
    CAS_RETRY_LOGIN = False
    CAS_APPLY_ATTRIBUTES_TO_USER = False
    
    # Αποθήκευση proxy-granting ticket (για μελλοντική χρήση)
    CAS_PROXY_CALLBACK = None
    
    # Θα γίνει χαρτογράφηση attributes από CAS στο callback
    CAS_USER_ATTRIBUTES_MAPPING = {
        'email': 'email',
        'first_name': 'first_name',
        'last_name': 'last_name',
    }
