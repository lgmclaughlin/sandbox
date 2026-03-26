#!/bin/bash
set -euo pipefail

WHITELIST_FILE="/etc/firewall/whitelist.txt"
IPSET_NAME="allowed-domains"
TEMP_IPSET="${IPSET_NAME}-temp"

if [[ ! -f "$WHITELIST_FILE" ]]; then
  echo "ERROR: whitelist.txt not found"
  exit 1
fi

ipset destroy "$TEMP_IPSET" 2>/dev/null || true
ipset create "$TEMP_IPSET" hash:net

echo "Applying firewall whitelist..."

FAILED_DOMAINS=""

while IFS= read -r line || [[ -n "$line" ]]; do
    domain="${line%%#*}"
    domain="$(echo "$domain" | xargs)"
    [[ -z "$domain" ]] && continue

    echo "Resolving $domain..."
    ips=$(dig +short A "$domain" +nocomments +noquestion | grep -E '^[0-9.]+$' || true)

    if [[ -n "$ips" ]]; then
        for ip in $ips; do
            ipset add "$TEMP_IPSET" "$ip" -exist
        done
    else
        echo "WARNING: Failed to resolve $domain to an IPv4 address"
        FAILED_DOMAINS="$FAILED_DOMAINS $domain"
    fi
done < "$WHITELIST_FILE"

if ipset list "$IPSET_NAME" >/dev/null 2>&1; then
    ipset swap "$TEMP_IPSET" "$IPSET_NAME"
    ipset destroy "$TEMP_IPSET"
else
    ipset rename "$TEMP_IPSET" "$IPSET_NAME"
fi

if [[ -n "$FAILED_DOMAINS" ]]; then
    echo "WARNING: The following domains failed to resolve:$FAILED_DOMAINS"
fi

echo "Done."
