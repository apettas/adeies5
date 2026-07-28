#!/bin/bash
# Email alert από fail2ban με ελληνικές οδηγίες
set -euo pipefail

NAME="${1:-unknown}"
IP="${2:-unknown}"
FAILURES="${3:-?}"
DEST="${4:-apettas@gmail.com}"
SENDER="${5:-andpettas@sch.gr}"
SENDERNAME="${6:-Adeies Fail2Ban}"

/usr/sbin/sendmail -f "$SENDER" "$DEST" <<EOF
Subject: [Adeies fail2ban] Ban ${NAME}: ${IP}
From: ${SENDERNAME} <${SENDER}>
To: ${DEST}
Content-Type: text/plain; charset=UTF-8

ALERT: Fail2Ban — αποκλεισμός IP
================================

Jail: ${NAME}
IP που αποκλείστηκε: ${IP}
Αποτυχίες: ${FAILURES}
Server: adeieshyperv25 (10.32.113.124)

Τι συνέβη
---------
Το fail2ban εντόπισε επαναλαμβανόμενες αποτυχημένες προσπάθειες
(π.χ. SSH brute-force ή κακόβουλα HTTP requests στα nginx logs)
και απαγόρευσε προσωρινά αυτή την IP στο firewall του server.

Γιατί ενεργοποιήθηκε
--------------------
Προστασία του SSH (και δευτερευόντως nginx) από αυτοματοποιημένες επιθέσεις.
Σημείωση: για το δημόσιο site μέσω Cloudflare Tunnel, το HTTP abuse
αντιμετωπίζεται καλύτερα στο Cloudflare WAF — το fail2ban SSH είναι το κρίσιμο.

Τι να κάνεις
------------
1. Αν η IP είναι δική σου (LAN/VPN): ξεμπλόκαρε με:
   sudo fail2ban-client set ${NAME} unbanip ${IP}
2. Αν είναι άγνωστη: άστο banned — είναι η επιθυμητή συμπεριφορά.
3. Έλεγχος: sudo fail2ban-client status ${NAME}
4. Αν πολλά bans από SSH: βάλε SSH keys και PasswordAuthentication no.

EOF
