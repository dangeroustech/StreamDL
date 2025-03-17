#!/bin/sh

./streamdl -config /app/config/config.yml -out /app/dl -move /app/out -time "${TICK_TIME:-60}" -log-level "${LOG_LEVEL:-info}" 