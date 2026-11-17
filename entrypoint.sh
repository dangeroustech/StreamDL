#!/bin/sh
# Create the runtime user from PUID/PGID, make the mounted folders writable, then
# start StreamDL as that user with the standard container paths. Like v3, the
# container command is ignored: settings come from the environment.
set -eu

: "${PUID:=1000}"
: "${PGID:=1000}"

if ! getent group "${PGID}" >/dev/null 2>&1; then
  groupadd -g "${PGID}" streamdl
fi
if ! getent passwd "${PUID}" >/dev/null 2>&1; then
  useradd -u "${PUID}" -g "${PGID}" -M -d /home/streamdl -s /usr/sbin/nologin streamdl
fi

# yt-dlp caches player data under $HOME/.cache
mkdir -p /app/dl /app/out /app/data /home/streamdl/.cache
chown "${PUID}:${PGID}" /app/dl /app/out /app/data 2>/dev/null || \
  echo "Could not change ownership on /app/dl, /app/out, or /app/data"
chown -R "${PUID}:${PGID}" /home/streamdl 2>/dev/null || true

set -- -config /app/config/config.yml -out /app/dl -move /app/out \
  -time "${TICK_TIME:-60}" -log-level "${LOG_LEVEL:-info}" -log-dest "${LOG_DEST:-file}" \
  -data /app/data
if [ -n "${LOG_FILE:-}" ]; then
  set -- "$@" -log-file "${LOG_FILE}"
fi

export HOME=/home/streamdl
export XDG_CACHE_HOME=/home/streamdl/.cache
exec gosu "${PUID}:${PGID}" /app/.venv/bin/python -m streamdl "$@"
