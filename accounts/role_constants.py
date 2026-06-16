"""
Κανονικοί κωδικοί ρόλων συστήματος (canonical set).

Όλος ο κώδικας πρέπει να χρησιμοποιεί αυτούς τους κωδικούς — όχι παλιές
lowercase παραλλαγές (employee, department_manager, administrator, κ.λπ.).
"""

ROLE_EMPLOYEE = 'EMPLOYEE'
ROLE_MANAGER = 'MANAGER'
ROLE_LEAVE_HANDLER = 'LEAVE_HANDLER'
ROLE_ADMIN = 'ADMIN'
ROLE_SECRETARY = 'SECRETARY'
ROLE_HR_ADMIN = 'HR_ADMIN'
ROLE_HR_OFFICER = 'HR_OFFICER'

CANONICAL_ROLE_CODES = frozenset({
    ROLE_EMPLOYEE,
    ROLE_MANAGER,
    ROLE_LEAVE_HANDLER,
    ROLE_ADMIN,
    ROLE_SECRETARY,
    ROLE_HR_ADMIN,
    ROLE_HR_OFFICER,
})

# Παλιοί κωδικοί → canonical (για migration και προσωρινή συμβατότητα)
LEGACY_ROLE_CODE_MAP = {
    'employee': ROLE_EMPLOYEE,
    'department_manager': ROLE_MANAGER,
    'leave_handler': ROLE_LEAVE_HANDLER,
    'administrator': ROLE_ADMIN,
    'hr_manager': ROLE_HR_ADMIN,
}


def normalize_role_code(code):
    """Επιστρέφει τον canonical κωδικό ρόλου."""
    if not code:
        return code
    return LEGACY_ROLE_CODE_MAP.get(code, code)
