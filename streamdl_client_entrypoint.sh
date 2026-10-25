#!/bin/sh

set -eu

LOG_LEVEL="${LOG_LEVEL:-info}"
LOG_DEST="${LOG_DEST:-file}"

if [ -n "${LOG_FILE:-}" ]; then
  exec ./streamdl \
    -config /app/config/config.yml \
    -out /app/dl \
    -move /app/out \
    -time "${TICK_TIME:-60}" \
    -log-level "${LOG_LEVEL}" \
    -log-dest "${LOG_DEST}" \
    -log-file "${LOG_FILE}" \
    -data /app/data
fi

exec ./streamdl \
  -config /app/config/config.yml \
  -out /app/dl \
  -move /app/out \
  -time "${TICK_TIME:-60}" \
  -log-level "${LOG_LEVEL}" \
  -log-dest "${LOG_DEST}" \
  -data /app/data
