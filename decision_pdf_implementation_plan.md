# Σχέδιο Υλοποίησης Δημιουργίας Απόφασης PDF

## Περιγραφή Workflow
Υλοποίηση 4-βηματικού workflow για τη δημιουργία και επεξεργασία αποφάσεων άδειας σε PDF μορφή με προεπισκόπηση και δυνατότητα επεξεργασίας.

## Βήμα 1: Προσθήκη Κουμπιού Έναρξης

### Αρχεία που θα τροποποιηθούν:
- `templates/leaves/detail.html` - Προσθήκη κουμπιού "Ετοιμασία Απόφασης"

### Υλοποίηση:
```html
<!-- Προσθήκη κουμπιού στο detail template -->
{% if user.is_staff and leave_request.status == 'FOR_PROTOCOL_PDEDE' %}
    <a href="{% url 'leaves:prepare_decision_preview' leave_request.id %}" 
       class="btn btn-primary">
        <i class="fas fa-file-alt"></i> Ετοιμασία Απόφασης
    </a>
{% endif %}
```

## Βήμα 2: Δημιουργία Template Tags & Utilities

### Αρχεία που θα δημιουργηθούν:
