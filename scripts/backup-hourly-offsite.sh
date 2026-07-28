#!/usr/bin/env bash
# Ωριαίο offsite backup (μόνο PostgreSQL) → Synology Hourly_Backup.
#
# Σκοπός: συχνά σημεία επαναφοράς για δεδομένα βάσης μέσα στην ημέρα.
# ΔΕΝ περιλαμβάνει media / private_media / συνημμένα — αυτά καλύπτονται από το
# ημερήσιο full backup (backup-offsite.sh). Τα συνημμένα αλλάζουν σπάνια·
# το ωριαίο full με αρχεία θα ήταν αργό και θα γέμιζε το NAS χωρίς όφελος.
#
# Απαιτούμενα στο .env:
#   SFTP_* (ίδια με το ημερήσιο), ALERT_EMAIL
#
# Προαιρετικά:
#   SFTP_HOURLY_REMOTE_DIR=To_Cloud/Adeies_Hyperv25_Backup/Hourly_Backup
#   HOURLY_RETENTION_HOURS=24   # κράτα backups νεότερα από N ώρες
#
# Χρήση:
#   ./scripts/backup-hourly-offsite.sh
#   make prod-backup-hourly
#
# Cron (κάθε ώρα):
#   5 * * * * /home/andre/adeies5/scripts/backup-hourly-offsite.sh >> /var/log/adeies5-backup-hourly.log 2>&1
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

STAMP="$(date +%Y%m%d_%H%M%S)"
LOG_PREFIX="[adeies5-hourly ${STAMP}]"
LOG_FILE="${LOG_FILE:-/var/log/adeies5-backup-hourly.log}"
TMP_DIR=""
FAILED=0
FAIL_REASON=""

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DB_NAME="${DB_NAME:-pdede_leaves}"
DB_USER="${DB_USER:-pdede_user}"
SFTP_HOST="${SFTP_HOST:-nikolas}"
SFTP_PORT="${SFTP_PORT:-22}"
SFTP_USER="${SFTP_USER:-andreas}"
SFTP_PASSWORD="${SFTP_PASSWORD:-}"
SFTP_IDENTITY="${SFTP_IDENTITY:-}"
SFTP_REMOTE_DIR="${SFTP_REMOTE_DIR:-To_Cloud/Adeies_Hyperv25_Backup}"
SFTP_HOURLY_REMOTE_DIR="${SFTP_HOURLY_REMOTE_DIR:-${SFTP_REMOTE_DIR}/Hourly_Backup}"
HOURLY_RETENTION_HOURS="${HOURLY_RETENTION_HOURS:-24}"
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
SFTP: ${SFTP_USER}@${SFTP_HOST}:${SFTP_PORT} → ${SFTP_HOURLY_REMOTE_DIR}
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
      "[PDEDE Leaves] ΑΠΟΤΥΧΙΑ hourly backup — $(hostname) $(date +%Y-%m-%d %H:%M)" \
      "Το ωριαίο backup (μόνο DB) απέτυχε.

Αιτία: ${reason}

Ενέργειες:
1. tail -100 ${LOG_FILE}
2. docker compose -f ${ROOT_DIR}/docker-compose.prod.yml ps
3. Ξανατρέξτε: ${ROOT_DIR}/scripts/backup-hourly-offsite.sh" || true
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
    fail "Το sshpass δεν βρέθηκε (apt install sshpass)"
  fi
  export SSHPASS="${SFTP_PASSWORD}"
  sshpass -e sftp "${opts[@]}" "${SFTP_USER}@${SFTP_HOST}" < "${batch_file}"
}

COMPOSE=(docker compose -f docker-compose.prod.yml)

if ! command -v docker >/dev/null 2>&1; then
  fail "Το docker δεν βρέθηκε"
fi
if ! "${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -qx db; then
  fail "Το service db δεν τρέχει"
fi

log "Έναρξη hourly backup (μόνο DB, χωρίς συνημμένα) → ${SFTP_HOURLY_REMOTE_DIR}"

TMP_DIR="$(mktemp -d /tmp/adeies5-hourly.XXXXXX)"
ARCHIVE_NAME="adeies5_hourly_${STAMP}.sql.gz"
ARCHIVE_PATH="${TMP_DIR}/${ARCHIVE_NAME}"

log "1/3 pg_dump..."
"${COMPOSE[@]}" exec -T db pg_dump -U "${DB_USER}" -d "${DB_NAME}" \
  | gzip -9 > "${ARCHIVE_PATH}" \
  || fail "Απέτυχε το pg_dump"

ARCHIVE_KB="$(du -sk "${ARCHIVE_PATH}" | awk '{print $1}')"
log "Dump μέγεθος: ${ARCHIVE_KB}KB"

# Δημιουργία υποφακέλου Hourly_Backup αν δεν υπάρχει + upload
log "2/3 SFTP upload..."
BATCH="${TMP_DIR}/sftp.batch"
{
  # mkdir είναι idempotent στο OpenSSH sftp (αγνοεί αν υπάρχει) — σε αποτυχία συνεχίζουμε
  echo "-mkdir ${SFTP_REMOTE_DIR}"
  echo "-mkdir ${SFTP_HOURLY_REMOTE_DIR}"
  echo "cd ${SFTP_HOURLY_REMOTE_DIR}"
  echo "put ${ARCHIVE_PATH} ${ARCHIVE_NAME}"
  echo "ls -l"
  echo "bye"
} > "${BATCH}"

if ! run_sftp "${BATCH}" > "${TMP_DIR}/sftp_upload.log" 2>&1; then
  cat "${TMP_DIR}/sftp_upload.log" >&2 || true
  fail "Απέτυχε το SFTP upload στο ${SFTP_HOST}"
fi
log "Upload OK"

# Retention: κράτα αρχεία νεότερα από HOURLY_RETENTION_HOURS (βάσει stamp στο όνομα)
log "3/3 Retention: ${HOURLY_RETENTION_HOURS} ώρες..."
LIST_BATCH="${TMP_DIR}/sftp_ls.batch"
{
  echo "cd ${SFTP_HOURLY_REMOTE_DIR}"
  echo "ls"
  echo "bye"
} > "${LIST_BATCH}"

REMOTE_LIST="$(run_sftp "${LIST_BATCH}" 2>/dev/null | awk '{print $NF}' | grep -E '^adeies5_hourly_[0-9]{8}_[0-9]{6}\.sql\.gz$' || true)"

# Cutoff ως epoch seconds
CUTOFF_EPOCH="$(date -d "-${HOURLY_RETENTION_HOURS} hours" +%s 2>/dev/null \
  || date -v-"${HOURLY_RETENTION_HOURS}"H +%s)"

RM_BATCH="${TMP_DIR}/sftp_rm.batch"
: > "${RM_BATCH}"
echo "cd ${SFTP_HOURLY_REMOTE_DIR}" >> "${RM_BATCH}"
DELETED=0
while IFS= read -r fname; do
  [[ -z "${fname}" ]] && continue
  # adeies5_hourly_YYYYMMDD_HHMMSS.sql.gz
  stamp="$(echo "${fname}" | sed -n 's/^adeies5_hourly_\([0-9]\{8\}\)_\([0-9]\{6\}\)\.sql\.gz$/\1 \2/p')"
  [[ -z "${stamp}" ]] && continue
  ymd="${stamp%% *}"
  hms="${stamp##* }"
  file_epoch="$(date -d "${ymd:0:4}-${ymd:4:2}-${ymd:6:2} ${hms:0:2}:${hms:2:2}:${hms:4:2}" +%s 2>/dev/null || true)"
  [[ -z "${file_epoch}" ]] && continue
  if (( file_epoch < CUTOFF_EPOCH )); then
    echo "rm ${fname}" >> "${RM_BATCH}"
    DELETED=$((DELETED + 1))
  fi
done <<< "${REMOTE_LIST}"
echo "bye" >> "${RM_BATCH}"

if (( DELETED > 0 )); then
  run_sftp "${RM_BATCH}" > "${TMP_DIR}/sftp_rm.log" 2>&1 \
    || log "ΠΡΟΕΙΔΟΠΟΙΗΣΗ: hourly retention απέτυχε μερικώς"
  log "Διαγράφηκαν ${DELETED} παλιά hourly backups"
else
  log "Κανένα παλιό hourly backup προς διαγραφή"
fi

log "Ολοκληρώθηκε — ${ARCHIVE_NAME} (${ARCHIVE_KB}KB) στο ${SFTP_HOURLY_REMOTE_DIR}"
FAILED=0
FAIL_REASON=""
exit 0
