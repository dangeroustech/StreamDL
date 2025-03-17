#!/bin/sh

# Default values for UID and GID
: ${PUID:=1000}
: ${PGID:=1000}

echo "Starting with UID: $PUID, GID: $PGID"

# Get group name if GID exists
EXISTING_GROUP=$(getent group "$PGID" | cut -d: -f1)

# Handle group creation or use existing
if [ -z "$EXISTING_GROUP" ]; then
    # GID doesn't exist, create new group
    addgroup -g "$PGID" streamdl
    GROUP_NAME="streamdl"
else
    # Use existing group
    GROUP_NAME="$EXISTING_GROUP"
    echo "Using existing group $GROUP_NAME for GID $PGID"
fi

# Create user if it doesn't exist
if ! getent passwd streamdl >/dev/null; then
    adduser -D -u "$PUID" -G "$GROUP_NAME" streamdl
fi

# Ensure app directories exist and have correct ownership
mkdir -p /app/dl /app/out
chown -R streamdl:"$GROUP_NAME" /app /app/dl /app/out

# Switch to the streamdl user and run the actual entrypoint
exec su-exec streamdl:"$GROUP_NAME" /app/streamdl_client_entrypoint.sh "$@"
