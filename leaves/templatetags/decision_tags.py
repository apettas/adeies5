from django import template

# Try to import num2words for better Greek number conversion
try:
    from num2words import num2words
    HAS_NUM2WORDS = True
except ImportError:
    HAS_NUM2WORDS = False

register = template.Library()

@register.filter
def to_accusative(name):
    """
    Μετατροπή πλήρους ονόματος από ονομαστική σε αιτιατική πτώση
    """
    if not name:
        return name
    
    # Διαχωρίζουμε όνομα και επώνυμο
    parts = name.strip().split()
    if len(parts) < 2:
        return name
    
    first_name = parts[0]
    last_name = parts[1]
    
    # Μετατροπή ονόματος σε αιτιατική
    first_name_accusative = convert_first_name_to_accusative(first_name)
    
    # Μετατροπή επωνύμου σε αιτιατική
    last_name_accusative = convert_last_name_to_accusative(last_name)
    
    return f"{first_name_accusative} {last_name_accusative}"

def convert_first_name_to_accusative(name):
    """Μετατροπή ονόματος σε αιτιατική πτώση"""
    # Ανδρικά ονόματα
    if name.endswith('ας'):
        return name[:-2] + 'α'  # Ανδρέας → Ανδρέα
    elif name.endswith('ης'):
        return name[:-2] + 'η'  # Γιάννης → Γιάννη
    elif name.endswith('ος'):
        return name[:-2] + 'ο'  # Νίκος → Νίκο
    elif name.endswith('ες'):
        return name[:-2] + 'η'  # Σωκράτης → Σωκράτη
    
    # Γυναικεία ονόματα (συνήθως μένουν ίδια στην αιτιατική)
    elif name.endswith('α'):
        return name  # Μαρία → Μαρία
    elif name.endswith('η'):
        return name  # Ελένη → Ελένη
    elif name.endswith('ω'):
        return name  # Καλλιρρόη → Καλλιρρόη
    
    # Αν δεν ταιριάζει κάποιος κανόνας, επιστρέφουμε το αρχικό
    return name

def convert_last_name_to_accusative(surname):
    """Μετατροπή επωνύμου σε αιτιατική πτώση"""
    # Ανδρικά επώνυμα
    if surname.endswith('ας'):
        return surname[:-2] + 'α'  # Πέττας → Πέττα
    elif surname.endswith('ης'):
        return surname[:-2] + 'η'  # Παπαδάκης → Παπαδάκη
    elif surname.endswith('ος'):
        return surname[:-2] + 'ο'  # Παπαδόπουλος → Παπαδόπουλο
    elif surname.endswith('ου'):
        return surname  # Γεωργίου → Γεωργίου (ήδη γενική, μένει ίδιο)
    
    # Γυναικεία επώνυμα (συνήθως μένουν ίδια)
    elif surname.endswith('α'):
        return surname  # Καρρά → Καρρά
    elif surname.endswith('η'):
        return surname  # Παπαδοπούλη → Παπαδοπούλη
    
    # Αν δεν ταιριάζει κάποιος κανόνας, επιστρέφουμε το αρχικό
    return surname

@register.filter
def convert_days_to_greek_genitive(days):
    """
    Μετατροπή αριθμού ημερών σε ελληνικές λέξεις σε γενική πτώση
    """
    if not days:
        return ""
    
    try:
        days_int = int(days)
        
        # Use num2words if available for better Greek number conversion
        if HAS_NUM2WORDS:
            try:
                # Try to get Greek number words
                greek_word = num2words(days_int, lang='el')
                # Convert to genitive case (simplified)
                if greek_word.endswith('ένα'):
                    return greek_word[:-3] + 'ενός'
                elif greek_word.endswith('δύο'):
                    return 'δύο'
                elif greek_word.endswith('τρία'):
                    return greek_word[:-4] + 'τριών'
                return greek_word
            except:
                # Fallback to manual conversion if num2words fails
                pass
        
        # Manual Greek number conversion (fallback)
        if days_int == 1:
            return "μίας"
        elif days_int == 2:
            return "δύο"
        elif days_int == 3:
            return "τριών"
        elif days_int == 4:
            return "τεσσάρων"
        elif days_int == 5:
            return "πέντε"
        elif days_int == 6:
            return "έξι"
        elif days_int == 7:
            return "επτά"
        elif days_int == 8:
            return "οκτώ"
        elif days_int == 9:
            return "εννέα"
        elif days_int == 10:
            return "δέκα"
        elif days_int == 11:
            return "έντεκα"
        elif days_int == 12:
            return "δώδεκα"
        elif days_int == 13:
            return "δεκατριών"
        elif days_int == 14:
            return "δεκατεσσάρων"
        elif days_int == 15:
            return "δεκαπέντε"
        elif days_int == 16:
            return "δεκαέξι"
        elif days_int == 17:
            return "δεκαεπτά"
        elif days_int == 18:
            return "δεκαοκτώ"
        elif days_int == 19:
            return "δεκαεννέα"
        elif days_int == 20:
            return "είκοσι"
        elif days_int == 21:
            return "είκοσι μίας"
        elif days_int == 22:
            return "είκοσι δύο"
        elif days_int == 30:
            return "τριάντα"
        else:
            # Για μεγαλύτερους αριθμούς, επιστρέφουμε τον αριθμό
            return str(days_int)
    except (ValueError, TypeError):
        return str(days)

@register.filter
def format_leave_dates(leave_request):
    """
    Μορφοποίηση των ημερομηνιών άδειας στα ελληνικά
    """
    if not leave_request.start_date:
        return ""
    
    # Ελληνικοί μήνες
    months = {
        1: "Ιανουαρίου", 2: "Φεβρουαρίου", 3: "Μαρτίου", 4: "Απριλίου",
        5: "Μαΐου", 6: "Ιουνίου", 7: "Ιουλίου", 8: "Αυγούστου",
        9: "Σεπτεμβρίου", 10: "Οκτωβρίου", 11: "Νοεμβρίου", 12: "Δεκεμβρίου"
    }
    
    start_date = leave_request.start_date
    start_formatted = f"{start_date.day} {months[start_date.month]} {start_date.year}"
    
    if leave_request.days_requested == 1:
        return f"στις {start_formatted}"
    else:
        end_date = leave_request.get_end_date()
        if end_date:
            end_formatted = f"{end_date.day} {months[end_date.month]} {end_date.year}"
            return f"από {start_formatted} έως {end_formatted}"
        else:
            return f"από {start_formatted}"

@register.filter
def greek_date_format(date):
    """
    Μορφοποίηση ημερομηνίας στα ελληνικά
    """
    if not date:
        return ""
    
    months = {
        1: "Ιανουαρίου", 2: "Φεβρουαρίου", 3: "Μαρτίου", 4: "Απριλίου",
        5: "Μαΐου", 6: "Ιουνίου", 7: "Ιουλίου", 8: "Αυγούστου",
        9: "Σεπτεμβρίου", 10: "Οκτωβρίου", 11: "Νοεμβρίου", 12: "Δεκεμβρίου"
    }
    
    return f"{date.day} {months[date.month]} {date.year}"