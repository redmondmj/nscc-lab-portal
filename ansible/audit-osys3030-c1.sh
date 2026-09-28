#!/bin/bash
# ==============================================================================
# OSYS3030 - Challenge 1 Audit Engine (Grade-A-Tron)
# Audits: SSH Key, NTP Sync, UID 0, Blank Passwords, Unattended Upgrades,
#         SSH Hardening (Port 2222, inet, no root, no pass), UFW Firewall
# Returns: Pure JSON
# ==============================================================================

# Target user detection
TARGET_USER="student"
if [ ! -d "/home/$TARGET_USER" ]; then
    TARGET_USER=$(awk -F: '($3 >= 1000 && $3 < 60000 && $1 != "nobody"){print $1; exit}' /etc/passwd)
fi

USER_HOME=$(getent passwd "$TARGET_USER" 2>/dev/null | cut -d: -f6)

# 1. SSH Authorized Keys check
if [ -n "$USER_HOME" ] && [ -s "$USER_HOME/.ssh/authorized_keys" ]; then
    CHECK_SSH_KEY=true
else
    CHECK_SSH_KEY=false
fi

# 2. NTP Time Sync check
if timedatectl status 2>/dev/null | grep -qE "(NTP service: active|synchronized: yes)" || systemctl is-active --quiet chrony 2>/dev/null; then
    CHECK_NTP=true
else
    CHECK_NTP=false
fi

# 3. UID 0 Non-root accounts check
EXTRA_ROOTS=$(awk -F: '($3=="0" && $1!="root"){print $1}' /etc/passwd)
if [ -z "$EXTRA_ROOTS" ]; then
    CHECK_UID0=true
else
    CHECK_UID0=false
fi

# 4. Blank passwords in shadow check
BLANK_PASS=$(awk -F: '($2 == ""){print $1}' /etc/shadow 2>/dev/null)
if [ -z "$BLANK_PASS" ]; then
    CHECK_BLANK_PASS=true
else
    CHECK_BLANK_PASS=false
fi

# 5. Unattended Upgrades package check
if dpkg -s unattended-upgrades >/dev/null 2>&1; then
    CHECK_UNATTENDED_PKG=true
else
    CHECK_UNATTENDED_PKG=false
fi

# 6. Unattended Upgrades service check
if systemctl is-active --quiet unattended-upgrades 2>/dev/null || systemctl is-enabled --quiet unattended-upgrades 2>/dev/null; then
    CHECK_UNATTENDED_SVC=true
else
    CHECK_UNATTENDED_SVC=false
fi

# SSH Hardening Checks (Evaluate active daemon runtime config via sshd -T)
SSHD_TEST=$(sshd -T 2>/dev/null)

# 7. SSH Port 2222
if echo "$SSHD_TEST" | grep -qi "^port 2222$"; then
    CHECK_SSH_PORT=true
else
    CHECK_SSH_PORT=false
fi

# 8. SSH AddressFamily inet
if echo "$SSHD_TEST" | grep -qi "^addressfamily inet$"; then
    CHECK_SSH_AF=true
else
    CHECK_SSH_AF=false
fi

# 9. SSH PermitRootLogin no
if echo "$SSHD_TEST" | grep -qi "^permitrootlogin no$"; then
    CHECK_SSH_ROOT=true
else
    CHECK_SSH_ROOT=false
fi

# 10. SSH PasswordAuthentication no
if echo "$SSHD_TEST" | grep -qi "^passwordauthentication no$"; then
    CHECK_SSH_PASS_AUTH=true
else
    CHECK_SSH_PASS_AUTH=false
fi

# 11. UFW Firewall Active
if ufw status 2>/dev/null | grep -qi "Status: active"; then
    CHECK_UFW_STATUS=true
else
    CHECK_UFW_STATUS=false
fi

# 12. UFW Rule for Port 2222
if ufw status 2>/dev/null | grep -qE "2222(/tcp)?\s+ALLOW"; then
    CHECK_UFW_RULE=true
else
    CHECK_UFW_RULE=false
fi

# Calculate score
TOTAL_CHECKS=12
PASSED_COUNT=0
for val in "$CHECK_SSH_KEY" "$CHECK_NTP" "$CHECK_UID0" "$CHECK_BLANK_PASS" \
           "$CHECK_UNATTENDED_PKG" "$CHECK_UNATTENDED_SVC" "$CHECK_SSH_PORT" \
           "$CHECK_SSH_AF" "$CHECK_SSH_ROOT" "$CHECK_SSH_PASS_AUTH" \
           "$CHECK_UFW_STATUS" "$CHECK_UFW_RULE"; do
    if [ "$val" = "true" ]; then
        PASSED_COUNT=$((PASSED_COUNT + 1))
    fi
done

SCORE_PCT=$(awk -v p="$PASSED_COUNT" -v t="$TOTAL_CHECKS" 'BEGIN { printf "%.1f", (p/t)*100 }')

# Output Clean JSON
cat <<EOF
{
  "Student": "{{ student_id | default(inventory_hostname) }}",
  "Host": "{{ inventory_hostname }}",
  "TargetUser": "$TARGET_USER",
  "TotalChecks": $TOTAL_CHECKS,
  "PassedCount": $PASSED_COUNT,
  "ScorePercent": $SCORE_PCT,
  "Checks": {
    "SSHKey": { "Pass": $CHECK_SSH_KEY, "Description": "authorized_keys exists and is non-empty" },
    "NTP": { "Pass": $CHECK_NTP, "Description": "NTP service or chrony active" },
    "UID0": { "Pass": $CHECK_UID0, "Description": "No rogue non-root accounts with UID 0" },
    "BlankPass": { "Pass": $CHECK_BLANK_PASS, "Description": "No accounts with blank passwords" },
    "UnattendedPkg": { "Pass": $CHECK_UNATTENDED_PKG, "Description": "unattended-upgrades package installed" },
    "UnattendedSvc": { "Pass": $CHECK_UNATTENDED_SVC, "Description": "unattended-upgrades service active/enabled" },
    "SSHPort": { "Pass": $CHECK_SSH_PORT, "Description": "sshd port is 2222" },
    "SSHAddressFamily": { "Pass": $CHECK_SSH_AF, "Description": "sshd AddressFamily is inet" },
    "SSHRootLogin": { "Pass": $CHECK_SSH_ROOT, "Description": "sshd PermitRootLogin is no" },
    "SSHPasswordAuth": { "Pass": $CHECK_SSH_PASS_AUTH, "Description": "sshd PasswordAuthentication is no" },
    "UFWStatus": { "Pass": $CHECK_UFW_STATUS, "Description": "ufw firewall is active" },
    "UFWRule": { "Pass": $CHECK_UFW_RULE, "Description": "ufw allows port 2222" }
  }
}
EOF
