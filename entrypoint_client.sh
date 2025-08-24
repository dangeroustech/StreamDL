#!/bin/sh

# Default values for UID and GID
: "${PUID:=1000}"
: "${PGID:=1000}"

echo "=== CLIENT ENTRYPOINT DEBUG ==="
echo "Environment PUID: ${PUID}, PGID: ${PGID}, UMASK: ${UMASK}"
echo "Current process UID: $(id -u), GID: $(id -g)"
echo "Current user: $(whoami)"

# Create user with specified UID/GID
echo "Creating user with UID=${PUID}, GID=${PGID}"
addgroup -g "${PGID}" streamdl 2>/dev/null || echo "Group exists"
adduser -D -u "${PUID}" -G streamdl streamdl 2>/dev/null || echo "User exists"

# Verify user was created
echo "Created user info: $(id streamdl 2>/dev/null || echo 'User not found')"

# Ensure download directories exist (don't modify mounted volumes)
echo "Setting up directories"
mkdir -p /app/dl /app/out 2>/dev/null || echo "Directories already exist (likely mounted)"

# Switch to the specified user and run the actual entrypoint
echo "Switching to user ${PUID}:${PGID}"
exec su-exec "${PUID}":"${PGID}" /app/streamdl_client_entrypoint.sh "$@"
