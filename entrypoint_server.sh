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
    groupadd -g "$PGID" streamdl
    GROUP_NAME="streamdl"
else
    # Use existing group
    GROUP_NAME="$EXISTING_GROUP"
    echo "Using existing group $GROUP_NAME for GID $PGID"
fi

# Create user if it doesn't exist
if ! getent passwd streamdl >/dev/null; then
    useradd -u "$PUID" -g "$GROUP_NAME" -s /bin/bash streamdl
fi

# Create and set up home directory and cache directories
mkdir -p /home/streamdl/.cache/uv
chown -R streamdl:"$GROUP_NAME" /home/streamdl
chmod 700 /home/streamdl

# Ensure app directory has correct ownership
chown -R streamdl:"$GROUP_NAME" /app

# Switch to the streamdl user and run the actual entrypoint
exec gosu streamdl:"$GROUP_NAME" /app/streamdl_server_entrypoint.sh "$@"
