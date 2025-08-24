#!/bin/sh

# Default values for UID and GID
: "${PUID:=1000}"
: "${PGID:=1000}"

# Create user with specified UID/GID
groupadd -g "${PGID}" streamdl 2>/dev/null || echo "Group exists"
useradd -u "${PUID}" -g streamdl -s /bin/bash streamdl 2>/dev/null || echo "User exists"

# Set up home directory for the user
mkdir -p /home/streamdl/.cache/uv
chown -R "${PUID}":"${PGID}" /home/streamdl 2>/dev/null || echo "Could not set home ownership"
chmod 700 /home/streamdl

# Set read permissions for virtual environment
chmod -R 755 /app/.venv 2>/dev/null || true
exec gosu "${PUID}":"${PGID}" /app/streamdl_server_entrypoint.sh "$@"
