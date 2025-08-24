#!/bin/sh

# Default values for UID and GID
: "${PUID:=1000}"
: "${PGID:=1000}"

# Create user with specified UID/GID
addgroup -g "${PGID}" streamdl 2>/dev/null || echo "Group exists"
adduser -D -u "${PUID}" -G streamdl streamdl 2>/dev/null || echo "User exists"

# Ensure download directories exist
mkdir -p /app/dl /app/out 2>/dev/null || echo "Directories already exist (likely mounted)"
exec su-exec "${PUID}":"${PGID}" /app/streamdl_client_entrypoint.sh "$@"
