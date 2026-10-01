#!/bin/bash
# ==============================================================================
# OSYS3030 - Challenge 2 Audit Engine (Grade-A-Tron)
# Audits: Multi-Homed Network Configuration
# Checks: ens18 WAN (Static, Default Gateway, DNS, Internet),
#         ens19 LAN (Link Up, 10.x IP, No Default Route, Netplan Config),
#         Extension 2 (Jumbo Frames MTU 9000)
# Returns: Pure JSON
# ==============================================================================

# Target user detection
TARGET_USER="student"
if [ ! -d "/home/$TARGET_USER" ]; then
    TARGET_USER=$(awk -F: '($3 >= 1000 && $3 < 60000 && $1 != "nobody"){print $1; exit}' /etc/passwd)
fi

# 1. ens18 WAN Link UP
if ip link show dev ens18 2>/dev/null | grep -q "state UP"; then
    CHECK_ENS18_UP=true
else
    CHECK_ENS18_UP=false
fi

# 2. Default route exists on ens18
DEFAULT_GW=$(ip route show default 2>/dev/null | awk '{print $3}' | head -n1)
DEFAULT_DEV=$(ip route show default 2>/dev/null | awk '{print $5}' | head -n1)
if [ -n "$DEFAULT_GW" ] && [ "$DEFAULT_DEV" = "ens18" ]; then
    CHECK_ENS18_GW=true
else
    CHECK_ENS18_GW=false
fi

# 3. ens19 LAN Adapter Exists
if ip link show dev ens19 >/dev/null 2>&1; then
    CHECK_ENS19_EXISTS=true
else
    CHECK_ENS19_EXISTS=false
fi

# 4. ens19 LAN Link UP
if ip link show dev ens19 2>/dev/null | grep -q "state UP"; then
    CHECK_ENS19_UP=true
else
    CHECK_ENS19_UP=false
fi

# 5. ens19 has valid 10.x.x.x private IP (e.g. 10.0.0.250/24 or 10.<ID>.0.250/24)
ENS19_IP=$(ip -4 -o addr show dev ens19 2>/dev/null | awk '{print $4}' | head -n1)
if echo "$ENS19_IP" | grep -qE "^10\.[0-9]+\.[0-9]+\.[0-9]+"; then
    CHECK_ENS19_IP=true
else
    CHECK_ENS19_IP=false
fi

# 6. No Default Route on ens19 (Correct multi-homed isolation: only WAN has default route)
if ip route show dev ens19 2>/dev/null | grep -q "default"; then
    CHECK_ENS19_NO_DEFAULT=false
else
    CHECK_ENS19_NO_DEFAULT=true
fi

# 7. Netplan defines ens19 configuration
if grep -rqsE "(ens19|10\.[0-9]+\.[0-9]+\.[0-9]+)" /etc/netplan/ 2>/dev/null; then
    CHECK_NETPLAN=true
else
    CHECK_NETPLAN=false
fi

# 8. Ping Default Gateway
if [ -n "$DEFAULT_GW" ] && ping -c 1 -W 2 "$DEFAULT_GW" >/dev/null 2>&1; then
    CHECK_PING_GW=true
else
    CHECK_PING_GW=false
fi

# 9. Ping Internet IP (8.8.8.8 or 1.1.1.1)
if ping -c 1 -W 2 8.8.8.8 >/dev/null 2>&1 || ping -c 1 -W 2 1.1.1.1 >/dev/null 2>&1; then
    CHECK_PING_INTERNET=true
else
    CHECK_PING_INTERNET=false
fi

# 10. DNS Resolution
if getent hosts google.com >/dev/null 2>&1 || ping -c 1 -W 2 google.com >/dev/null 2>&1; then
    CHECK_DNS=true
else
    CHECK_DNS=false
fi

# 11. Extension 2: Jumbo Frames MTU 9000 on ens19
ENS19_MTU=$(cat /sys/class/net/ens19/mtu 2>/dev/null || echo "1500")
if [ "$ENS19_MTU" = "9000" ]; then
    CHECK_MTU_9000=true
else
    CHECK_MTU_9000=false
fi

# Calculate score
TOTAL_CHECKS=11
PASSED_COUNT=0
for val in "$CHECK_ENS18_UP" "$CHECK_ENS18_GW" "$CHECK_ENS19_EXISTS" "$CHECK_ENS19_UP" \
           "$CHECK_ENS19_IP" "$CHECK_ENS19_NO_DEFAULT" "$CHECK_NETPLAN" \
           "$CHECK_PING_GW" "$CHECK_PING_INTERNET" "$CHECK_DNS" "$CHECK_MTU_9000"; do
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
  "Ens19MTU": $ENS19_MTU,
  "Ens19IP": "${ENS19_IP:-none}",
  "DefaultGateway": "${DEFAULT_GW:-none}",
  "Checks": {
    "Ens18Up": { "Pass": $CHECK_ENS18_UP, "Description": "WAN interface ens18 link is UP" },
    "Ens18Gateway": { "Pass": $CHECK_ENS18_GW, "Description": "Default route is assigned via ens18" },
    "Ens19Exists": { "Pass": $CHECK_ENS19_EXISTS, "Description": "LAN interface ens19 virtual hardware adapter exists" },
    "Ens19Up": { "Pass": $CHECK_ENS19_UP, "Description": "LAN interface ens19 link is UP" },
    "Ens19IP": { "Pass": $CHECK_ENS19_IP, "Description": "Static 10.x.x.x private IP assigned to ens19" },
    "Ens19NoDefault": { "Pass": $CHECK_ENS19_NO_DEFAULT, "Description": "No default gateway on ens19 (clean multi-homing)" },
    "NetplanConfig": { "Pass": $CHECK_NETPLAN, "Description": "Netplan defines ens19 configuration" },
    "PingGateway": { "Pass": $CHECK_PING_GW, "Description": "Default gateway is reachable via ping" },
    "PingInternet": { "Pass": $CHECK_PING_INTERNET, "Description": "Public IP (8.8.8.8/1.1.1.1) is reachable" },
    "DNSResolution": { "Pass": $CHECK_DNS, "Description": "DNS resolution is functional" },
    "JumboFrames": { "Pass": $CHECK_MTU_9000, "Description": "Extension 2: MTU 9000 configured on ens19" }
  }
}
EOF
