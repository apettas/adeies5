#!/usr/bin/env bash
# Πλήρης ρύθμιση monitoring & security (τρέχει στο host VM)
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Netdata email config ==="
bash "${ROOT_DIR}/monitoring/netdata/render-config.sh"

echo ""
echo "=== fail2ban ==="
bash "${ROOT_DIR}/monitoring/fail2ban/install.sh"

echo ""
echo "=== Ολοκληρώθηκε ==="
echo "1. Τρέξτε: make prod-build && make prod-up && make prod-migrate"
echo "2. Netdata UI: http://127.0.0.1:19999"
echo "3. Uptime Kuma: http://127.0.0.1:3001 (ρυθμίστε monitor για https://sadeies.pdede.gov.gr/health/)"
