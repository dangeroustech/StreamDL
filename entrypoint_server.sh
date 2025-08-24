#!/bin/sh

# Default values for UID and GID
: "${PUID:=1000}"
: "${PGID:=1000}"

echo "Starting with UID: ${PUID}, GID: ${PGID}, UMASK: ${UMASK}"

# Check if we're running as root
if [ "$(id -u)" -eq 0 ] 2>/dev/null || true; then
	# We're root, can do admin operations
	ROOT_MODE=true
else
	# We're not root, skip admin operations
	ROOT_MODE=false
	echo "Running as non-root user, skipping admin operations"
fi

# Get group name if GID exists
if [ "${ROOT_MODE}" = true ]; then
	EXISTING_GROUP=$(getent group "${PGID}" | cut -d: -f1)

	# Handle group creation or use existing
	if [ -z "${EXISTING_GROUP}" ]; then
		# GID doesn't exist, create new group
		groupadd -g "${PGID}" streamdl
		GROUP_NAME="streamdl"
	else
		# Use existing group
		GROUP_NAME="${EXISTING_GROUP}"
		echo "Using existing group ${GROUP_NAME} for GID ${PGID}"
	fi

	# Create user if it doesn't exist
	if ! getent passwd streamdl >/dev/null; then
		useradd -u "${PUID}" -g "${GROUP_NAME}" -s /bin/bash streamdl
	fi
else
	# Use existing user/group names
	GROUP_NAME="streamdl"
fi

# Create and set up home directory and cache directories
if [ "${ROOT_MODE}" = true ]; then
	mkdir -p /home/streamdl/.cache/uv
	chown -R streamdl:"${GROUP_NAME}" /home/streamdl 2>/dev/null || true
	chmod 700 /home/streamdl 2>/dev/null || true

	# Ensure app directory has correct ownership (excluding .venv)
	find /app -path "/app/.venv" -prune -o -path "/app/.pdm-build" -prune -o -print0 | xargs -0 chown streamdl:"${GROUP_NAME}" 2>/dev/null || true
	# Set specific permissions for .venv directory to allow read access
	chmod -R 755 /app/.venv 2>/dev/null || true

	# Switch to the streamdl user and run the actual entrypoint
	exec gosu streamdl:"${GROUP_NAME}" /app/streamdl_server_entrypoint.sh "$@"
else
	# Already running as target user, just run the entrypoint
	exec /app/streamdl_server_entrypoint.sh "$@"
fi
