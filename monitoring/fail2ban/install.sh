#!/usr/bin/env bash
# Εγκατάσταση fail2ban configs στο host VM (τρέχει εκτός Docker)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
F2B_SRC="${ROOT_DIR}/monitoring/fail2ban"
NGINX_LOGPATH="${ROOT_DIR}/logs/nginx"

if [[ ! -d "${NGINX_LOGPATH}" ]]; then
  mkdir -p "${NGINX_LOGPATH}"
fi

if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

ALERT_EMAIL="${ALERT_EMAIL:-apettas@gmail.com}"
NGINX_LOGPATH="${NGINX_LOGPATH:-${ROOT_DIR}/logs/nginx}"

if ! command -v fail2ban-client >/dev/null 2>&1; then
  echo "Εγκατάσταση fail2ban και mailutils..."
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y fail2ban mailutils msmtp msmtp-mta
  elif command -v dnf >/dev/null 2>&1; then
    sudo dnf install -y fail2ban mailx
  else
    echo "Εγκαταστήστε χειροκίνητα: fail2ban + mailutils/mailx"
    exit 1
  fi
fi

# fail2ban αρνείται να ξεκινήσει αν λείπουν τα log αρχεία
sudo mkdir -p "${NGINX_LOGPATH}"
sudo touch "${NGINX_LOGPATH}/access.log" "${NGINX_LOGPATH}/error.log"

sudo mkdir -p /etc/fail2ban/jail.d /etc/fail2ban/filter.d

# jail με σωστό logpath
sed "s|%(nginx_logpath)s|${NGINX_LOGPATH}|g" \
  "${F2B_SRC}/jail.d/pdede-leaves.local" \
  | sudo tee /etc/fail2ban/jail.d/pdede-leaves.local >/dev/null

sudo cp "${F2B_SRC}/filter.d/nginx-botsearch-pdede.conf" \
  /etc/fail2ban/filter.d/nginx-botsearch-pdede.conf

# msmtp στο host για email alerts από fail2ban (ίδιο SMTP με Django/Netdata)
if [[ -n "${EMAIL_HOST_USER:-}" && -n "${EMAIL_HOST_PASSWORD:-}" ]]; then
  sudo tee /etc/msmtprc >/dev/null <<EOF
defaults
auth           on
tls            on
tls_starttls   off
host           ${EMAIL_HOST:-mail.sch.gr}
port           ${EMAIL_PORT:-465}
from           ${DEFAULT_FROM_EMAIL:-${EMAIL_HOST_USER}}
user           ${EMAIL_HOST_USER}
password       ${EMAIL_HOST_PASSWORD}
account        default
EOF
  sudo chmod 600 /etc/msmtprc
fi

# Ενημέρωση email παραλήπτη
sudo sed -i "s|^destemail = .*|destemail = ${ALERT_EMAIL}|" \
  /etc/fail2ban/jail.d/pdede-leaves.local

# Απενεργοποίηση sshd jail αν δεν υπάρχει auth.log
if [[ ! -f /var/log/auth.log ]]; then
  echo "Προειδοποίηση: /var/log/auth.log δεν υπάρχει — απενεργοποίηση sshd jail"
  sudo sed -i '/\[sshd\]/,/^\[/ s/^enabled  = true/enabled  = false/' \
    /etc/fail2ban/jail.d/pdede-leaves.local
fi

echo "Έλεγχος fail2ban configuration..."
if ! sudo fail2ban-client -t; then
  echo ""
  echo "ΣΦΑΛΜΑ: Άκυρη fail2ban configuration. Τελευταία logs:"
  sudo journalctl -u fail2ban -n 30 --no-pager || true
  exit 1
fi

sudo systemctl enable fail2ban
if ! sudo systemctl restart fail2ban; then
  echo ""
  echo "ΣΦΑΛΜΑ: Αποτυχία εκκίνησης fail2ban. Τελευταία logs:"
  sudo journalctl -u fail2ban -n 30 --no-pager || true
  exit 1
fi

sleep 2

echo "fail2ban εγκαταστάθηκε. Παραλήπτης alerts: ${ALERT_EMAIL}"
echo "Nginx logs: ${NGINX_LOGPATH}"

if sudo fail2ban-client status >/dev/null 2>&1; then
  sudo fail2ban-client status
else
  echo ""
  echo "Προειδοποίηση: fail2ban configs εγκαταστάθηκαν αλλά το service δεν απαντά."
  echo "Δείτε: sudo journalctl -u fail2ban -n 50"
  exit 1
fi
