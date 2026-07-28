#!/usr/bin/env bash
# Πλήρες backup adeies5 → τοπικά + SFTP στο Synology, με email alert σε αποτυχία.
#
# Περιλαμβάνει: pg_dump + media + private_media + ρυθμίσεις (via backup-local.sh)
# Μετά ανεβάζει ένα tar στο SFTP και εφαρμόζει remote retention.
#
# Απαιτούμενα στο .env (ή περιβάλλον):
#   SFTP_HOST=nikolas
#   SFTP_PORT=22
#   SFTP_USER=andreas
#   SFTP_PASSWORD=...          # ή SFTP_IDENTITY=~/.ssh/adeies5_sftp_nikolas
#   SFTP_REMOTE_DIR=To_Cloud/Adeies_Hyperv25_Backup
#   ALERT_EMAIL=apettas@gmail.com
#
# Προαιρετικά:
#   LOCAL_RETENTION_DAYS=3     # τοπικά (ίδιος δίσκος VM)
#   OFFSITE_RETENTION_DAYS=30  # στο Synology
#   BACKUP_ROOT=/var/backups/adeies5
#
# Χρήση:
#   ./scripts/backup-offsite.sh
#   make prod-backup-offsite
#
# Cron (καθημερινά 02:30):
#   30 2 * * * /home/andre/adeies5/scripts/backup-offsite.sh >> /var/log/adeies5-backup-offsite.log 2>&1
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_PREFIX="[adeies5-offsite ${STAMP}]"
LOG_FILE="${LOG_FILE:-/var/log/adeies5-backup-offsite.log}"
TMP_DIR=""
FAILED=0
FAIL_REASON=""

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/adeies5}"
LOCAL_RETENTION_DAYS="${LOCAL_RETENTION_DAYS:-3}"
OFFSITE_RETENTION_DAYS="${OFFSITE_RETENTION_DAYS:-30}"
SFTP_HOST="${SFTP_HOST:-nikolas}"
SFTP_PORT="${SFTP_PORT:-22}"
SFTP_USER="${SFTP_USER:-andreas}"
SFTP_PASSWORD="${SFTP_PASSWORD:-}"
SFTP_IDENTITY="${SFTP_IDENTITY:-}"
SFTP_REMOTE_DIR="${SFTP_REMOTE_DIR:-To_Cloud/Adeies_Hyperv25_Backup}"
ALERT_EMAIL="${ALERT_EMAIL:-apettas@gmail.com}"
DEFAULT_FROM_EMAIL="${DEFAULT_FROM_EMAIL:-${EMAIL_HOST_USER:-adeiespdede@sch.gr}}"

log() { echo "${LOG_PREFIX} $*"; }

send_alert() {
  local subject="$1"
  local body="$2"
  local mail_body

  mail_body="$(cat <<EOF
${body}

---
Hostname: $(hostname)
Ώρα: $(date '+%Y-%m-%d %H:%M:%S %Z')
Project: ${ROOT_DIR}
SFTP: ${SFTP_USER}@${SFTP_HOST}:${SFTP_PORT} → ${SFTP_REMOTE_DIR}
Log: ${LOG_FILE}
EOF
)"

  if command -v msmtp >/dev/null 2>&1; then
    if printf 'From: %s\nTo: %s\nSubject: %s\nContent-Type: text/plain; charset=UTF-8\n\n%s\n' \
      "${DEFAULT_FROM_EMAIL}" "${ALERT_EMAIL}" "${subject}" "${mail_body}" \
      | msmtp --read-envelope-from --read-recipients; then
      log "Email alert στάλθηκε στο ${ALERT_EMAIL}"
      return 0
    fi
    log "ΠΡΟΕΙΔΟΠΟΙΗΣΗ: msmtp απέτυχε — δοκιμή Django send_mail"
  fi

  if command -v docker >/dev/null 2>&1 \
    && docker compose -f docker-compose.prod.yml ps --status running --services 2>/dev/null | grep -qx web; then
    local b64
    b64="$(printf '%s' "${mail_body}" | base64 | tr -d '\n')"
    docker compose -f docker-compose.prod.yml exec -T web python manage.py shell -c "
from django.core.mail import send_mail
from django.conf import settings
import base64
body = base64.b64decode('${b64}').decode('utf-8')
send_mail(
    subject='${subject//\'/\\\'}',
    message=body,
    from_email=settings.DEFAULT_FROM_EMAIL,
    recipient_list=['${ALERT_EMAIL}'],
    fail_silently=False,
)
print('Email sent')
" && log "Email alert στάλθηκε (Django) στο ${ALERT_EMAIL}" && return 0
  fi

  log "ΣΦΑΛΜΑ: δεν στάλθηκε email alert στο ${ALERT_EMAIL}"
  return 1
}

on_exit() {
  local rc=$?
  [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]] && rm -rf "${TMP_DIR}" || true
  if (( FAILED != 0 || rc != 0 )); then
    local reason="${FAIL_REASON:-άγνωστο σφάλμα (exit ${rc})}"
    log "ΑΠΟΤΥΧΙΑ: ${reason}"
    send_alert \
      "[PDEDE Leaves] ΑΠΟΤΥΧΙΑ backup — $(hostname) $(date +%Y-%m-%d)" \
      "Το offsite backup απέτυχε.

Αιτία: ${reason}

Ενέργειες:
1. ssh στο $(hostname) και δείτε: tail -100 ${LOG_FILE}
2. Ελέγξτε docker: cd ${ROOT_DIR} && docker compose -f docker-compose.prod.yml ps
3. Ελέγξτε SFTP: nc -zv ${SFTP_HOST} ${SFTP_PORT}
4. Ξανατρέξτε: ${ROOT_DIR}/scripts/backup-offsite.sh" || true
    exit 1
  fi
}
trap on_exit EXIT

fail() {
  FAIL_REASON="$*"
  FAILED=1
  exit 1
}

run_sftp() {
  local batch_file="$1"
  local -a opts=(-o StrictHostKeyChecking=accept-new -P "${SFTP_PORT}")

  if [[ -n "${SFTP_IDENTITY}" && -f "${SFTP_IDENTITY}" ]]; then
    sftp "${opts[@]}" -i "${SFTP_IDENTITY}" -o BatchMode=yes \
      -o PreferredAuthentications=publickey \
      "${SFTP_USER}@${SFTP_HOST}" < "${batch_file}"
    return $?
  fi

  if [[ -z "${SFTP_PASSWORD}" ]]; then
    fail "Ορίστε SFTP_PASSWORD ή SFTP_IDENTITY στο .env"
  fi
  if ! command -v sshpass >/dev/null 2>&1; then
    fail "Το sshpass δεν βρέθηκε (apt install sshpass) — χρειάζεται για password SFTP"
  fi
  export SSHPASS="${SFTP_PASSWORD}"
  sshpass -e sftp "${opts[@]}" "${SFTP_USER}@${SFTP_HOST}" < "${batch_file}"
}

log "Έναρξη offsite backup"

# 1) Τοπικό full backup
log "1/3 Τοπικό backup (RETENTION_DAYS=${LOCAL_RETENTION_DAYS})..."
if ! RETENTION_DAYS="${LOCAL_RETENTION_DAYS}" BACKUP_ROOT="${BACKUP_ROOT}" \
  bash "${ROOT_DIR}/scripts/backup-local.sh"; then
  fail "Απέτυχε το τοπικό backup (backup-local.sh)"
fi

LATEST="${BACKUP_ROOT}/latest"
if [[ ! -d "${LATEST}" ]]; then
  fail "Δεν βρέθηκε ${LATEST} μετά το τοπικό backup"
fi

# Resolve πραγματικό stamp dir (symlink)
BACKUP_DIR="$(readlink -f "${LATEST}")"
BACKUP_NAME="$(basename "${BACKUP_DIR}")"
ARCHIVE_NAME="adeies5_${BACKUP_NAME}.tar"
TMP_DIR="$(mktemp -d /tmp/adeies5-offsite.XXXXXX)"
ARCHIVE_PATH="${TMP_DIR}/${ARCHIVE_NAME}"

log "2/3 Δημιουργία archive ${ARCHIVE_NAME}..."
tar -C "${BACKUP_ROOT}" -cf "${ARCHIVE_PATH}" "${BACKUP_NAME}" \
  || fail "Απέτυχε η δημιουργία του tar archive"

ARCHIVE_MB="$(du -sm "${ARCHIVE_PATH}" | awk '{print $1}')"
log "Archive μέγεθος: ${ARCHIVE_MB}MB"

# 3) Upload + remote retention
log "3/3 SFTP upload → ${SFTP_USER}@${SFTP_HOST}:${SFTP_REMOTE_DIR}/"
BATCH="${TMP_DIR}/sftp.batch"
{
  echo "cd ${SFTP_REMOTE_DIR}"
  echo "put ${ARCHIVE_PATH} ${ARCHIVE_NAME}"
  echo "ls -l"
  echo "bye"
} > "${BATCH}"

if ! run_sftp "${BATCH}" > "${TMP_DIR}/sftp_upload.log" 2>&1; then
  cat "${TMP_DIR}/sftp_upload.log" >&2 || true
  fail "Απέτυχε το SFTP upload στο ${SFTP_HOST}"
fi
log "Upload OK"

# Remote retention βάσει ημερομηνίας στο όνομα αρχείου (adeies5_YYYYMMDD_HHMMSS.tar)
if (( OFFSITE_RETENTION_DAYS > 0 )); then
  log "Remote retention: διαγραφή παλαιότερων από ${OFFSITE_RETENTION_DAYS} ημέρες..."
  LIST_BATCH="${TMP_DIR}/sftp_ls.batch"
  {
    echo "cd ${SFTP_REMOTE_DIR}"
    echo "ls"
    echo "bye"
  } > "${LIST_BATCH}"

  REMOTE_LIST="$(run_sftp "${LIST_BATCH}" 2>/dev/null | awk '{print $NF}' | grep -E '^adeies5_20[0-9]{6}_[0-9]{6}\.tar$' || true)"
  CUTOFF="$(date -d "-${OFFSITE_RETENTION_DAYS} days" +%Y%m%d 2>/dev/null \
    || date -v-"${OFFSITE_RETENTION_DAYS}"d +%Y%m%d)"

  RM_BATCH="${TMP_DIR}/sftp_rm.batch"
  : > "${RM_BATCH}"
  echo "cd ${SFTP_REMOTE_DIR}" >> "${RM_BATCH}"
  DELETED=0
  while IFS= read -r fname; do
    [[ -z "${fname}" ]] && continue
    # adeies5_YYYYMMDD_HHMMSS.tar → YYYYMMDD
    fdate="$(echo "${fname}" | sed -n 's/^adeies5_\([0-9]\{8\}\)_.*/\1/p')"
    [[ -z "${fdate}" ]] && continue
    if [[ "${fdate}" < "${CUTOFF}" ]]; then
      echo "rm ${fname}" >> "${RM_BATCH}"
      DELETED=$((DELETED + 1))
    fi
  done <<< "${REMOTE_LIST}"
  echo "bye" >> "${RM_BATCH}"

  if (( DELETED > 0 )); then
    run_sftp "${RM_BATCH}" > "${TMP_DIR}/sftp_rm.log" 2>&1 \
      || log "ΠΡΟΕΙΔΟΠΟΙΗΣΗ: remote retention απέτυχε μερικώς (δείτε log)"
    log "Διαγράφηκαν ${DELETED} παλιά remote backups"
  else
    log "Κανένα παλιό remote backup προς διαγραφή"
  fi
fi

log "Ολοκληρώθηκε επιτυχώς — ${ARCHIVE_NAME} (${ARCHIVE_MB}MB) στο ${SFTP_REMOTE_DIR}"
FAILED=0
FAIL_REASON=""
exit 0
