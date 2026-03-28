#!/bin/bash

# Firewall container entrypoint.
# Starts ulogd2 for NFLOG packet capture, then the firewall log daemon
# to parse ulogd output into unified event envelopes.

# Ensure log directories exist (bind mount may be empty)
mkdir -p /var/log/sandbox/firewall

# Start ulogd2 to capture NFLOG packets from iptables
ulogd -d -c /etc/ulogd.conf 2>/dev/null || true

# Start the firewall log daemon in background
/usr/local/bin/firewall-log.sh &

# Keep container alive
exec sleep infinity
