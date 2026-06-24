#!/usr/bin/env bash
# Πλήρες τοπικό backup adeies5 (DB + media + ρυθμίσεις).
#
# Ένας δίσκος 200GB (χωρίς ξεχωριστό mount):
#   BACKUP_ROOT=/var/backups/adeies5  (default — ίδιος δίσκος με VM)
#   Κρατήστε RETENTION_DAYS χαμηλά (3–7) και παρακολουθείτε: df -h /
#
# Χρήση:
#   ./scripts/backup-local.sh
#   make prod-backup-full
#   RETENTION_DAYS=5 ./scripts/backup-local.sh
#
# Cron (καθημερινά 02:30):
#   30 2 * * * /home/andre/adeies5/scripts/backup-local.sh >> /var/log/adeies5-backup.log 2>&1
#
# Σημαντικό: τοπικό backup στον ίδιο δίσκο ≠ αντικατάσταση offsite backup (Synology).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/adeies5}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
MIN_FREE_GB="${MIN_FREE_GB:-15}"
WARN_DISK_USE_PCT="${WARN_DISK_USE_PCT:-80}"
STAMP="$(date +%Y%m%d_%H%M%S)"
DEST="${BACKUP_ROOT}/${STAMP}"
LOG_PREFIX="[adeies5-backup ${STAMP}]"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

DB_NAME="${DB_NAME:-pdede_leaves}"
DB_USER="${DB_USER:-pdede_user}"

log() { echo "${LOG_PREFIX} $*"; }
die() { log "ΣΦΑΛΜΑ: $*"; exit 1; }

if ! command -v docker >/dev/null 2>&1; then
  die "Το docker δεν βρέθηκε"
fi

if ! docker compose version >/dev/null 2>&1; then
  die "Το docker compose δεν βρέθηκε"
fi

COMPOSE=(docker compose -f docker-compose.prod.yml)

if ! "${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -qx db; then
  die "Το service db δεν τρέχει — docker compose -f docker-compose.prod.yml up -d"
fi

if [[ ! -d "${BACKUP_ROOT}" ]]; then
  log "Δημιουργία ${BACKUP_ROOT}..."
  sudo mkdir -p "${BACKUP_ROOT}"
  sudo chown "$(id -un)":"$(id -gn)" "${BACKUP_ROOT}"
fi

DISK_USE_PCT="$(df -P "${BACKUP_ROOT}" | awk 'NR==2 {gsub(/%/,"",$5); print $5}')"
if (( DISK_USE_PCT >= WARN_DISK_USE_PCT )); then
  log "ΠΡΟΕΙΔΟΠΟΙΗΣΗ: ο δίσκος είναι ${DISK_USE_PCT}% γεμάτος (όριο ${WARN_DISK_USE_PCT}%)"
fi

FREE_KB="$(df -Pk "${BACKUP_ROOT}" | awk 'NR==2 {print $4}')"
FREE_GB=$((FREE_KB / 1024 / 1024))
if (( FREE_GB < MIN_FREE_GB )); then
  die "Λιγότερα από ${MIN_FREE_GB}GB ελεύθερα στο ${BACKUP_ROOT} (έχετε ${FREE_GB}GB)"
fi

find_volume() {
  local suffix="$1"
  docker volume ls -q --format '{{.Name}}' | grep "_${suffix}$" | head -n 1
}

MEDIA_VOL="$(find_volume media_volume)"
PRIVATE_VOL="$(find_volume private_media_volume)"

if [[ -z "${MEDIA_VOL}" || -z "${PRIVATE_VOL}" ]]; then
  die "Δεν βρέθηκαν Docker volumes media/private_media (τρέξτε prod-up πρώτα)"
fi

mkdir -p "${DEST}"
log "Προορισμός: ${DEST} (ελεύθερα ${FREE_GB}GB)"

log "1/4 PostgreSQL dump..."
"${COMPOSE[@]}" exec -T db pg_dump -U "${DB_USER}" -d "${DB_NAME}" | gzip -9 > "${DEST}/db.sql.gz"

log "2/4 media_volume (${MEDIA_VOL})..."
docker run --rm \
  -v "${MEDIA_VOL}:/data:ro" \
  -v "${DEST}:/backup" \
  alpine:3.20 \
  tar czf "/backup/media_volume.tar.gz" -C /data .

log "3/4 private_media_volume (${PRIVATE_VOL})..."
docker run --rm \
  -v "${PRIVATE_VOL}:/data:ro" \
  -v "${DEST}:/backup" \
  alpine:3.20 \
  tar czf "/backup/private_media_volume.tar.gz" -C /data .

log "4/4 Ρυθμίσεις..."
CONFIG_DIR="${DEST}/config"
mkdir -p "${CONFIG_DIR}"
[[ -f .env ]] && cp .env "${CONFIG_DIR}/.env"
cp docker-compose.prod.yml "${CONFIG_DIR}/"
cp nginx.prod.conf "${CONFIG_DIR}/" 2>/dev/null || true
[[ -d nginx ]] && cp -r nginx "${CONFIG_DIR}/nginx"

cat > "${DEST}/manifest.txt" <<EOF
timestamp=${STAMP}
hostname=$(hostname)
backup_root=${BACKUP_ROOT}
db_name=${DB_NAME}
media_volume=${MEDIA_VOL}
private_media_volume=${PRIVATE_VOL}
EOF

ln -sfn "${DEST}" "${BACKUP_ROOT}/latest"

TOTAL_MB="$(du -sm "${DEST}" | awk '{print $1}')"
log "Ολοκληρώθηκε — μέγεθος ${TOTAL_MB}MB στο ${DEST}"

if (( RETENTION_DAYS > 0 )); then
  log "Διαγραφή backups παλαιότερων από ${RETENTION_DAYS} ημέρες..."
  find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d \
    -name '20[0-9][0-9][0-9][0-9][0-9][0-9]_*' \
    -mtime "+${RETENTION_DAYS}" \
    -exec rm -rf {} +
fi

FREE_AFTER_GB="$(df -Pk "${BACKUP_ROOT}" | awk 'NR==2 {print int($4/1024/1024)}')"
log "Ελεύθερος χώρος μετά το backup: ${FREE_AFTER_GB}GB"
