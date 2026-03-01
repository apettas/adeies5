# Docker Users Guide - Εφαρμογή Αρχείου Δημιουργίας Χρηστών

## Εισαγωγή

Αυτός ο οδηγός εξηγεί πώς να εφαρμόσετε το αρχείο `andreas_users.py` για δημιουργία χρηστών στο Docker Desktop.

## Προαπαιτούμενα

- Docker Desktop εγκατεστημένο και ενεργό
- Docker Compose εγκατεστημένο
- Το project να τρέχει σε Docker containers

## Βήμα 1: Εκκίνηση του Docker Environment

Πρώτα, βεβαιωθείτε ότι όλα τα containers τρέχουν:

```bash
# Εκκίνηση όλων των υπηρεσιών
docker-compose up -d

# Έλεγχος κατάστασης
docker-compose ps
```

Περιμένετε μέχρι όλα τα containers να είναι σε κατάσταση "Up" και "healthy".

## Βήμα 2: Εκτέλεση του Αρχείου Δημιουργίας Χρηστών

Μόλις το περιβάλλον είναι έτοιμο, εκτελέστε το αρχείο δημιουργίας χρηστών:

```bash
# Εκτέλεση του management command για δημιουργία χρηστών
docker-compose exec web python manage.py andreas_users
```

## Βήμα 3: Επαλήθευση Δημιουργίας Χρηστών

Μετά την εκτέλεση, μπορείτε να επαληθεύσετε τη δημιουργία των χρηστών:

```bash
# Είσοδος στο Django shell για έλεγχο
docker-compose exec web python manage.py shell

# Στο shell, εκτελέστε:
# from django.contrib.auth import get_user_model
# User = get_user_model()
# users = User.objects.all()
# for user in users:
#     print(f"{user.email} - {user.full_name} - {user.department}")
# exit()
```

Ή απλά επισκεφτείτε το admin panel:
- URL: http://localhost:8000/admin
- Στοιχεία: admin@pdede.gr / admin123
- Πλοηγηθείτε σε "Users" για να δείτε τους δημιουργημένους χρήστες

## Βήμα 4: Εναλλακτικές Μέθοδοι

### Εκτέλεση από το Container

Αν προτιμάτε να εκτελέσετε το command από μέσα του container:

```bash
# Είσοδος στο container
docker-compose exec web bash

# Εκτέλεση του command
python manage.py andreas_users

# Έξοδος από το container
exit
```

### Εκτέλεση με Custom Parameters

Αν το αρχείο δέχεται παραμέτρους:

```bash
# Παράδειγμα με παραμέτρους (αν υποστηρίζονται)
docker-compose exec web python manage.py andreas_users --param1 value1 --param2 value2
```

## Συνήθη Προβλήματα και Λύσεις

### Πρόβλημα: Η βάση δεν είναι έτοιμη

```bash
# Έλεγχος κατάστασης βάσης
docker-compose exec db pg_isready -U pdede_user

# Αναμονή και επανάληψη
sleep 10
docker-compose exec web python manage.py andreas_users
```

### Πρόβλημα: Μη ύπαρξη dependencies

```bash
# Εκτέλεση migrations αν χρειάζεται
docker-compose exec web python manage.py migrate

# Επανάληψη της εκτέλεσης
docker-compose exec web python manage.py andreas_users
```

### Πρόβλημα: Χρήστες υπάρχουν ήδη

Το αρχείο έχει έλεγχο για ύπαρξη χρηστών, οπότε αν υπάρχουν ήδη, θα εμφανιστεί μήνυμα:
```
Χρήστης υπάρχει ήδη: user@example.com
```

### Πρόβλημα: Permission errors

```bash
# Έλεγχος και διόρθωση permissions
docker-compose exec web ls -la /app/
docker-compose exec web chown -R app:app /app/
```

## Πλήρης Ροή Εργασίας

```bash
# 1. Εκκίνηση περιβάλλοντος
docker-compose up -d

# 2. Έλεγχος κατάστασης
docker-compose ps

# 3. Περιμονή για health checks (περίπου 30-60 δευτερόλεπτα)
sleep 60

# 4. Εκτέλεση δημιουργίας χρηστών
docker-compose exec web python manage.py andreas_users

# 5. Έλεγχος αποτελεσμάτων
docker-compose exec web python manage.py shell
# Στο shell: User.objects.all().count()
```

## Παραδείγματα Εξόδου

### Επιτυχής Εκτέλεση

```
Έναρξη φόρτωσης χρηστών...
Φόρτωση χρηστών...
  Δημιουργήθηκε χρήστης: apettas@sch.gr (Ανδρέας Πέττας)
  Δημιουργήθηκε χρήστης: tolia@sch.gr (Κορίνα Τόλια)
  Δημιουργήθηκε χρήστης: korsianou@sch.gr (Κατερίνα Κορσιάνου)
Ολοκλήρωση φόρτωσης χρηστών!
Ολοκλήρωση φόρτωσης χρηστών!
```

### Χρήστες Υπάρχουν Ήδη

```
Έναρξη φόρτωσης χρηστών...
Φόρτωση χρηστών...
  Χρήστης υπάρχει ήδη: apettas@sch.gr
  Χρήστης υπάρχει ήδη: tolia@sch.gr
Ολοκλήρωση φόρτωσης χρηστών!
Ολοκλήρωση φόρτωσης χρηστών!
```

## Συμβουλές και Καλές Πρακτικές

1. **Πάντα ελέγχετε την κατάσταση των containers πριν την εκτέλεση**
2. **Χρησιμοποιείτε το `docker-compose logs -f web` για real-time monitoring**
3. **Αποθηκεύετε backups πριν από μαζικές εισαγωγές δεδομένων**
4. **Χρησιμοποιείτε transactions για ασφαλή εισαγωγή δεδομένων**
5. **Ελέγχετε τα logs για πιθανά σφάλματα**

## Επιπλέον Χρήσιμες Εντολές

```bash
# Παρακολούθηση logs σε real-time
docker-compose logs -f web

# Έλεγχος χώρου που καταλαμβάνουν τα containers
docker system df

# Καθαρισμός όλων των containers και volumes
docker-compose down -v
docker system prune -a

# Επανεκκίνηση συγκεκριμένου container
docker-compose restart web
```

## Υποστήριξη

Αν αντιμετωπίσετε προβλήματα:

1. Ελέγξτε τα logs: `docker-compose logs -f`
2. Επαληθεύστε την κατάσταση: `docker-compose ps`
3. Δοκιμάστε να εκτελέσετε το command χωρίς Docker για debugging
4. Δημιουργήστε issue στο repository με λεπτομέρειες του προβλήματος