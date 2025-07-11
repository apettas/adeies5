# Docker Setup για το Σύστημα Διαχείρισης Αδειών ΠΔΕΔΕ

## Προαπαιτούμενα

- Docker
- Docker Compose
- Git

## Γρήγορη Εκκίνηση (Development)

1. **Κλωνοποίηση του repository:**
```bash
git clone <repository-url>
cd adeies5
```

2. **Δημιουργία αρχείου περιβάλλοντος:**
```bash
cp .env.example .env
```

3. **Εκκίνηση των υπηρεσιών:**
```bash
docker-compose up -d
```

4. **Πρόσβαση στην εφαρμογή:**
- Εφαρμογή: http://localhost:8000
- Admin: http://localhost:8000/admin
- Στοιχεία σύνδεσης: admin@pdede.gr / admin123

## Δομή Docker

### Υπηρεσίες

- **db**: PostgreSQL 15 βάση δεδομένων
- **redis**: Redis για caching και sessions
- **web**: Django εφαρμογή
- **nginx**: Reverse proxy και static files server

### Volumes

- `postgres_data`: Δεδομένα βάσης
- `static_volume`: Static αρχεία
- `media_volume`: Media αρχεία
- `private_media_volume`: Κρυπτογραφημένα αρχεία

## Χρήσιμες Εντολές

### Development

```bash
# Εκκίνηση όλων των υπηρεσιών
docker-compose up -d

# Παρακολούθηση logs
docker-compose logs -f web

# Εκτέλεση Django εντολών
docker-compose exec web python fix_migrations.py
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py collectstatic

# Διόρθωση migration conflicts
docker-compose exec web python fix_migrations.py

# Είσοδος στο container
docker-compose exec web bash

# Σταμάτημα υπηρεσιών
docker-compose down

# Σταμάτημα και διαγραφή volumes
docker-compose down -v
```

### Production

```bash
# Εκκίνηση production setup
docker-compose -f docker-compose.prod.yml up -d

# Backup βάσης δεδομένων
docker-compose -f docker-compose.prod.yml --profile backup run backup

# Παρακολούθηση logs
docker-compose -f docker-compose.prod.yml logs -f
```

## Διαχείριση Βάσης Δεδομένων

### Backup

```bash
# Χειροκίνητο backup
docker-compose exec db pg_dump -U pdede_user pdede_leaves > backup.sql

# Αυτόματο backup (production)
docker-compose -f docker-compose.prod.yml --profile backup run backup
```

### Restore

```bash
# Restore από backup
docker-compose exec -T db psql -U pdede_user pdede_leaves < backup.sql
```

## Ρυθμίσεις Περιβάλλοντος

### Development (.env)

```env
DEBUG=True
SECRET_KEY=development-key
DB_PASSWORD=pdede_password
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Production (.env)

```env
DEBUG=False
SECRET_KEY=your-strong-secret-key
DB_PASSWORD=strong-database-password
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

## SSL/HTTPS Setup (Production)

1. **Δημιουργία SSL certificates:**
```bash
mkdir ssl
# Αντιγραφή των certificates στο φάκελο ssl/
```

2. **Ενεργοποίηση HTTPS στο nginx.conf:**
```bash
# Uncomment τα HTTPS blocks στο nginx.conf
```

3. **Ενημέρωση .env:**
```env
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

## Monitoring και Logs

### Logs

```bash
# Όλες οι υπηρεσίες
docker-compose logs -f

# Συγκεκριμένη υπηρεσία
docker-compose logs -f web
docker-compose logs -f db
docker-compose logs -f nginx

# Τελευταίες 100 γραμμές
docker-compose logs --tail=100 web
```

### Health Checks

```bash
# Έλεγχος κατάστασης containers
docker-compose ps

# Λεπτομερής έλεγχος
docker inspect <container_name>
```

## Troubleshooting

### Συνήθη Προβλήματα

1. **Σφάλμα σύνδεσης βάσης:**
```bash
# Έλεγχος αν η βάση είναι έτοιμη
docker-compose exec db pg_isready -U pdede_user

# Restart της βάσης
docker-compose restart db
```

2. **Πρόβλημα με static files:**
```bash
# Συλλογή static files
docker-compose exec web python manage.py collectstatic --clear
```

3. **Πρόβλημα με migrations:**
```bash
# Εκτέλεση migrations
docker-compose exec web python manage.py migrate

# Έλεγχος κατάστασης migrations
docker-compose exec web python manage.py showmigrations
```

4. **Πρόβλημα με permissions:**
```bash
# Διόρθωση permissions
docker-compose exec web chown -R app:app /app
```

## Ασφάλεια

### Production Checklist

- [ ] Αλλαγή default passwords
- [ ] Ρύθμιση SSL certificates
- [ ] Ενεργοποίηση security headers
- [ ] Περιορισμός πρόσβασης στη βάση δεδομένων
- [ ] Regular backups
- [ ] Monitoring και alerting
- [ ] Firewall rules

### Backup Strategy

- Καθημερινά αυτόματα backups
- Εβδομαδιαία full backups
- Μηνιαία archival backups
- Test restore procedures

## Υποστήριξη

Για προβλήματα ή ερωτήσεις, δημιουργήστε issue στο repository.