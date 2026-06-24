#!/usr/bin/env bash
# Γρήγορη διάγνωση production adeies5 — τρέξτε στο VM (adeies.pdede.gov.gr) και στείλτε το output.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

COMPOSE=(docker compose -f docker-compose.prod.yml)

# Πρώτο domain από ALLOWED_HOSTS (.env) για δοκιμές HTTP
APP_HOST="adeies.pdede.gov.gr"
if [[ -f .env ]]; then
  _hosts="$(grep -E '^ALLOWED_HOSTS=' .env | cut -d= -f2- | tr -d ' ')"
  if [[ -n "${_hosts}" ]]; then
    APP_HOST="${_hosts%%,*}"
  fi
fi

section() {
  echo ""
  echo "========== $* =========="
}

section "1. Host — χώρος & μνήμη"
df -h / || true
free -h || true

section "2. Docker services"
"${COMPOSE[@]}" ps -a 2>/dev/null || docker compose -f docker-compose.prod.yml ps -a

section "3. Health endpoints (τοπικά) — APP_HOST=${APP_HOST}"
echo -n "nginx static /health/: "
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: ${APP_HOST}" http://127.0.0.1/health/ 2>/dev/null || echo "FAIL"

echo -n "django μέσω nginx (/login/): "
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: ${APP_HOST}" http://127.0.0.1/login/ 2>/dev/null || echo "FAIL"

echo -n "gunicorn :8000 /health/ (127.0.0.1): "
"${COMPOSE[@]}" exec -T web curl -sf http://127.0.0.1:8000/health/ 2>/dev/null && echo "OK" || echo "FAIL (προσθέστε 127.0.0.1 στο ALLOWED_HOSTS)"

echo -n "gunicorn :8000 /login/ (Host=${APP_HOST}): "
"${COMPOSE[@]}" exec -T web curl -sf -o /dev/null -w "%{http_code}\n" -H "Host: ${APP_HOST}" http://127.0.0.1:8000/login/ 2>/dev/null || echo "FAIL"

section "4. Web logs (τελευταίες 40 γραμμές)"
"${COMPOSE[@]}" logs web --tail=40 2>/dev/null || true

section "5. Nginx logs (errors)"
tail -20 logs/nginx/error.log 2>/dev/null || echo "(no error.log)"

section "6. DB"
"${COMPOSE[@]}" exec -T db pg_isready -U "${DB_USER:-pdede_user}" 2>/dev/null || \
  "${COMPOSE[@]}" exec -T db pg_isready 2>/dev/null || echo "DB not ready"

section "7. Cloudflare tunnel (αν εγκατεστημένο)"
if systemctl is-active cloudflared &>/dev/null; then
  systemctl status cloudflared --no-pager -l 2>/dev/null | head -15
elif docker ps --format '{{.Names}}' 2>/dev/null | grep -qi cloudflare; then
  docker ps --filter name=cloudflare
else
  echo "cloudflared: δεν βρέθηκε ως systemd/docker — ελέγξτε χειροκίνητα"
fi

section "8. .env (χωρίς secrets)"
if [[ -f .env ]]; then
  grep -E '^(DEBUG|ALLOWED_HOSTS|CSRF_TRUSTED|CAS_|DB_NAME|NGINX_)' .env | sed 's/PASSWORD=.*/PASSWORD=***/'
else
  echo "ΔΕΝ ΥΠΑΡΧΕΙ .env"
fi

section "9. Τελευταία migrations"
"${COMPOSE[@]}" exec -T web python manage.py showmigrations --plan 2>/dev/null | tail -15 || true

echo ""
echo "=== Τέλος διάγνωσης $(date) ==="
