#!/bin/sh

# Default values for UID and GID
: "${PUID:=1000}"
: "${PGID:=1000}"

echo "Starting with UID: ${PUID}, GID: ${PGID}, UMASK: ${UMASK}"

# Check if we're running as root
CURRENT_UID=$(id -u 2>/dev/null)
echo "DEBUG: Current UID is ${CURRENT_UID}"
if [ "${CURRENT_UID}" -eq 0 ]; then
	# We're root, can do admin operations
	ROOT_MODE=true
	echo "DEBUG: Running as root, will do admin operations"
else
	# We're not root, skip admin operations
	ROOT_MODE=false
	echo "DEBUG: Running as non-root user, skipping admin operations"
fi

# Get group name if GID exists
if [ "${ROOT_MODE}" = true ]; then
	EXISTING_GROUP=$(getent group "${PGID}" | cut -d: -f1)

	# Handle group creation or use existing
	if [ -z "${EXISTING_GROUP}" ]; then
		# GID doesn't exist, create new group
		addgroup -g "${PGID}" streamdl
		GROUP_NAME="streamdl"
	else
		# Use existing group
		GROUP_NAME="${EXISTING_GROUP}"
		echo "Using existing group ${GROUP_NAME} for GID ${PGID}"
	fi

	# Create user if it doesn't exist
	if ! getent passwd streamdl >/dev/null; then
		adduser -D -u "${PUID}" -G "${GROUP_NAME}" streamdl
	fi

	# Ensure download directories exist and have correct ownership
	mkdir -p /app/dl /app/out
	chown -R streamdl:"${GROUP_NAME}" /app/dl /app/out 2>/dev/null || true

	# Switch to the streamdl user and run the actual entrypoint
	exec su-exec streamdl:"${GROUP_NAME}" /app/streamdl_client_entrypoint.sh "$@"
else
	# Ensure download directories exist
	mkdir -p /app/dl /app/out 2>/dev/null || true

	# Already running as target user, just run the entrypoint
	exec /app/streamdl_client_entrypoint.sh "$@"
fi
