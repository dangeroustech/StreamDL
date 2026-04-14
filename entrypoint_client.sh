#!/bin/sh

# Default values for UID and GID
: "${PUID:=1000}"
: "${PGID:=1000}"

# Create user with specified UID/GID
if ! getent group "${PGID}" >/dev/null 2>&1; then
  addgroup -g "${PGID}" streamdl
fi
if ! getent passwd "${PUID}" >/dev/null 2>&1; then
  adduser -D -u "${PUID}" -G streamdl streamdl
fi

# Ensure download and data directories exist and are writable by the runtime user
mkdir -p /app/dl /app/out /app/data
chown "${PUID}:${PGID}" /app/dl /app/out /app/data 2>/dev/null || \
  echo "Could not change ownership on /app/dl, /app/out, or /app/data"
exec su-exec "${PUID}":"${PGID}" /app/streamdl_client_entrypoint.sh "$@"
