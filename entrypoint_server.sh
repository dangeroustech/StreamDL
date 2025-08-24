#!/bin/sh

# Default values for UID and GID
: "${PUID:=1000}"
: "${PGID:=1000}"

echo "=== SERVER ENTRYPOINT DEBUG ==="
echo "Environment PUID: ${PUID}, PGID: ${PGID}, UMASK: ${UMASK}"
echo "Current process UID: $(id -u), GID: $(id -g)"
echo "Current user: $(whoami)"

# Create user with specified UID/GID
echo "Creating user with UID=${PUID}, GID=${PGID}"
groupadd -g "${PGID}" streamdl 2>/dev/null || echo "Group exists"
useradd -u "${PUID}" -g streamdl -s /bin/bash streamdl 2>/dev/null || echo "User exists"

# Verify user was created
echo "Created user info: $(id streamdl 2>/dev/null || echo 'User not found')"

# Set up home directory for the user
echo "Setting up home directory"
mkdir -p /home/streamdl/.cache/uv
chown -R "${PUID}":"${PGID}" /home/streamdl 2>/dev/null || echo "Could not set home ownership"
chmod 700 /home/streamdl

# Set read permissions for virtual environment
echo "Setting venv permissions"
chmod -R 755 /app/.venv 2>/dev/null || true

# Switch to the specified user and run the actual entrypoint
echo "Switching to user ${PUID}:${PGID}"
exec gosu "${PUID}":"${PGID}" /app/streamdl_server_entrypoint.sh "$@"
