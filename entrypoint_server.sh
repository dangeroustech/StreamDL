#!/bin/sh

# Default values for UID and GID
: "${PUID:=1000}"
: "${PGID:=1000}"

# Create user with specified UID/GID
if ! getent group "${PGID}" >/dev/null 2>&1; then
  groupadd -g "${PGID}" streamdl
fi
if ! getent passwd "${PUID}" >/dev/null 2>&1; then
  useradd -u "${PUID}" -g "${PGID}" -s /bin/bash -m -d /home/streamdl streamdl
fi

# Set up home directory for the user
mkdir -p /home/streamdl/.cache/uv
chown -R "${PUID}":"${PGID}" /home/streamdl 2>/dev/null || echo "Could not set home ownership"
chmod 700 /home/streamdl

# Set read permissions for virtual environment
chmod -R 755 /app/.venv 2>/dev/null || true
exec gosu "${PUID}":"${PGID}" /app/streamdl_server_entrypoint.sh "$@"
