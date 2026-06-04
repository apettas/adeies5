# Staging Deployment

This project is ready to run on a staging server with Docker Compose, PostgreSQL,
Redis, Gunicorn, and Nginx.

## 1. Server prerequisites

- Linux VPS/VM with Docker and Docker Compose installed.
- DNS record for the staging host, for example `staging.example.gr`.
- Firewall allowing only SSH, HTTP, and HTTPS:
  - `22/tcp`
  - `80/tcp`
  - `443/tcp`

## 2. Clone and configure

```bash
git clone <repo-url>
cd adeies5
cp .env.staging.example .env
```

Edit `.env` and set:

- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- database password
- email credentials
- protocol recipient

Do not commit `.env`.

## 3. First deploy

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

Check status and logs:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f nginx
```

## 4. HTTPS

The included `nginx.prod.conf` works over HTTP and forwards requests to Django.
For online staging, put HTTPS in front of it with a reverse proxy such as Caddy,
Traefik, or a host-level Nginx/Certbot setup.

If the HTTPS proxy runs on the same server, set the app Nginx to an internal
host port in `.env`:

```env
NGINX_HTTP_PORT=8080
```

Then point the HTTPS proxy to `http://127.0.0.1:8080`.

After HTTPS is confirmed working, update `.env`:

```env
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
CSRF_TRUSTED_ORIGINS=https://staging.example.gr
```

Optional HSTS for staging:

```env
SECURE_HSTS_SECONDS=3600
SECURE_HSTS_INCLUDE_SUBDOMAINS=False
SECURE_HSTS_PRELOAD=False
```

Restart after changes:

```bash
docker compose -f docker-compose.prod.yml up -d
```

## 5. Updates

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
```

## 6. Backups

Run a manual database backup:

```bash
docker compose -f docker-compose.prod.yml --profile backup run --rm backup
```

Also back up the Docker volumes that contain uploaded files:

- `media_volume`
- `private_media_volume`

## 7. Notes

- Default admin creation is disabled. Use `createsuperuser`, or set
  `CREATE_DEFAULT_SUPERUSER=True` with `DJANGO_SUPERUSER_EMAIL` and
  `DJANGO_SUPERUSER_PASSWORD` for a one-time bootstrap.
- Keep staging data separate from production data.
- If real data is copied into staging, anonymize sensitive personal data first.
