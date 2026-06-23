#!/usr/bin/env bash
# Δημιουργεί msmtprc και health_alarm_notify.conf από το .env
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
NETDATA_DIR="${ROOT_DIR}/monitoring/netdata"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Δεν βρέθηκε ${ENV_FILE}. Αντιγράψτε .env.example σε .env και συμπληρώστε SMTP credentials."
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

ALERT_EMAIL="${ALERT_EMAIL:-apettas@gmail.com}"
EMAIL_HOST="${EMAIL_HOST:-mail.sch.gr}"
EMAIL_PORT="${EMAIL_PORT:-465}"
EMAIL_HOST_USER="${EMAIL_HOST_USER:-}"
EMAIL_HOST_PASSWORD="${EMAIL_HOST_PASSWORD:-}"
DEFAULT_FROM_EMAIL="${DEFAULT_FROM_EMAIL:-${EMAIL_HOST_USER}}"

if [[ -z "${EMAIL_HOST_USER}" || -z "${EMAIL_HOST_PASSWORD}" ]]; then
  echo "Προειδοποίηση: EMAIL_HOST_USER ή EMAIL_HOST_PASSWORD λείπουν — τα email alerts μπορεί να μην λειτουργήσουν."
fi

mkdir -p "${NETDATA_DIR}"

cat > "${NETDATA_DIR}/msmtprc" <<EOF
# Αυτόματη δημιουργία από monitoring/netdata/render-config.sh — μην επεξεργαστείτε χειροκίνητα
defaults
auth           on
tls            on
tls_starttls   off
host           ${EMAIL_HOST}
port           ${EMAIL_PORT}
from           ${DEFAULT_FROM_EMAIL}
user           ${EMAIL_HOST_USER}
password       ${EMAIL_HOST_PASSWORD}

account        default
logfile        /var/log/msmtp.log
EOF
chmod 600 "${NETDATA_DIR}/msmtprc"

echo "Δημιουργία health_alarm_notify.conf από Netdata image..."
docker run --rm --entrypoint cat netdata/netdata:stable \
  /usr/lib/netdata/conf.d/health_alarm_notify.conf \
  > "${NETDATA_DIR}/health_alarm_notify.conf"

sed -i.bak \
  -e 's/^SEND_EMAIL="AUTO"/SEND_EMAIL="YES"/' \
  -e "s/^DEFAULT_RECIPIENT_EMAIL=\"root\"/DEFAULT_RECIPIENT_EMAIL=\"${ALERT_EMAIL}\"/" \
  -e "s/^EMAIL_SENDER=\"\"/EMAIL_SENDER=\"${DEFAULT_FROM_EMAIL}\"/" \
  "${NETDATA_DIR}/health_alarm_notify.conf"
rm -f "${NETDATA_DIR}/health_alarm_notify.conf.bak"

echo "OK: ${NETDATA_DIR}/msmtprc"
echo "OK: ${NETDATA_DIR}/health_alarm_notify.conf (παραλήπτης: ${ALERT_EMAIL})"
