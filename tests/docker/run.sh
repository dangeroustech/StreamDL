#!/usr/bin/env bash
# Run a command inside the throwaway dev container, e.g.
#   tests/docker/run.sh uv run pytest -q
#   PYTHON_VERSION=3.15 tests/docker/run.sh uv run pytest -q
# The repo is bind-mounted at /src and the command runs as your UID, so any files it
# writes (uv.lock, fixtures) are owned by you. The venv and uv cache live in named
# Docker volumes; remove them with:
#   docker volume rm streamdl-dev-venv-py3.14 streamdl-dev-venv-py3.15 streamdl-dev-uv-cache
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PY="${PYTHON_VERSION:-3.14}"
IMAGE="streamdl-dev:py${PY}"

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker build -q -t "$IMAGE" --build-arg PYTHON_VERSION="$PY" \
    -f "$ROOT/tests/docker/Dockerfile.dev" "$ROOT/tests/docker" >/dev/null
fi

# --init reaps orphaned grandchildren (post-script tests rely on it)
exec docker run --rm -i --init \
  --user "$(id -u):$(id -g)" \
  -v "$ROOT":/src \
  -v "streamdl-dev-venv-py${PY}":/venv \
  -v streamdl-dev-uv-cache:/uv-cache \
  "$IMAGE" "$@"
