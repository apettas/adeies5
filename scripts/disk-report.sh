#!/usr/bin/env bash
# Αναφορά χώρου δίσκου — αποστέλλεται στο ALERT_EMAIL (.env).
#
# Χρήση:
#   ./scripts/disk-report.sh
#   make disk-report
#
# Cron — 1η και 15η κάθε μήνα, 09:00:
#   0 9 1,15 * * /home/andre/adeies5/scripts/disk-report.sh >> /var/log/adeies5-disk-report.log 2>&1
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

WARN_DISK_USE_PCT="${WARN_DISK_USE_PCT:-75}"
REPORT_FILE="$(mktemp)"
trap 'rm -f "${REPORT_FILE}"' EXIT

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

ALERT_EMAIL="${ALERT_EMAIL:-apettas@gmail.com}"
SUBJECT="[PDEDE Leaves] Αναφορά δίσκου — $(date +%Y-%m-%d)"

COMPOSE=(docker compose -f docker-compose.prod.yml)

{
  echo "Αναφορά χώρου δίσκου — $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "Hostname: $(hostname)"
  echo "Project: ${ROOT_DIR}"
  echo ""

  DISK_USE_PCT="$(df -P / | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
  DISK_USE_HUMAN="$(df -h / | awk 'NR==2 {print $3 " used / " $2 " total (" $5 ")"}')"
  echo "=== Σύνοψη / ==="
  echo "Χρήση: ${DISK_USE_HUMAN}"
  echo ""

  if (( DISK_USE_PCT >= WARN_DISK_USE_PCT )); then
    echo "!!! ΠΡΟΕΙΔΟΠΟΙΗΣΗ: ο δίσκος είναι ${DISK_USE_PCT}% γεμάτος (όριο ${WARN_DISK_USE_PCT}%)"
    echo "    Εξετάστε: RETENTION_DAYS=3 στο backup, docker system prune, καθάρισμα παλιών logs"
    echo ""
  fi

  echo "=== df -h / ==="
  df -h /
  echo ""

  echo "=== du -sh (backups, docker, project) ==="
  du -sh /var/backups/adeies5 2>/dev/null || echo "/var/backups/adeies5: (δεν υπάρχει)"
  du -sh /var/lib/docker 2>/dev/null || echo "/var/lib/docker: (δεν υπάρχει)"
  du -sh "${ROOT_DIR}/backups" 2>/dev/null || echo "${ROOT_DIR}/backups: (δεν υπάρχει)"
  du -sh "${ROOT_DIR}/logs" 2>/dev/null || echo "${ROOT_DIR}/logs: (δεν υπάρχει)"
  echo ""

  if [[ -d /var/backups/adeies5 ]]; then
    echo "=== Τελευταία backups (/var/backups/adeies5) ==="
    du -sh /var/backups/adeies5/* 2>/dev/null | sort -hr | head -10 || true
    echo ""
  fi

  echo "=== docker system df ==="
  docker system df 2>/dev/null || echo "(docker system df απέτυχε)"
  echo ""

  echo "=== docker compose services ==="
  "${COMPOSE[@]}" ps 2>/dev/null || true
} > "${REPORT_FILE}"

if ! "${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -qx web; then
  echo "ΣΦΑΛΜΑ: το service web δεν τρέχει — δεν στάλθηκε email" >&2
  cat "${REPORT_FILE}"
  exit 1
fi

B64_REPORT="$(base64 < "${REPORT_FILE}" | tr -d '\n')"

"${COMPOSE[@]}" exec -T web python manage.py shell -c "
from django.core.mail import send_mail
from django.conf import settings
import base64

body = base64.b64decode('${B64_REPORT}').decode('utf-8')
recipient = '${ALERT_EMAIL}' or getattr(settings, 'ALERT_EMAIL', None) or 'apettas@gmail.com'
send_mail(
    subject='${SUBJECT}',
    message=body,
    from_email=settings.DEFAULT_FROM_EMAIL,
    recipient_list=[recipient],
    fail_silently=False,
)
print('Email sent to', recipient)
"

echo "Αναφορά δίσκου στάλθηκε στο ${ALERT_EMAIL}"
