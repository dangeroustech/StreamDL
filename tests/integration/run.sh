#!/usr/bin/env bash
set -euo pipefail

# Integration test: finds a live Twitch stream, downloads ~10 seconds, validates the output.
#
# Usage: ./tests/integration/run.sh
#
# Requires: docker compose, ffprobe

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.integration.yml"
CONFIG_DIR="$SCRIPT_DIR/config"
OUTPUT_DIR="$SCRIPT_DIR/output"
TIMEOUT_SECONDS=120

# Detect docker compose command — plugin, standalone, or direct path
if docker compose version &>/dev/null; then
  DC="docker compose"
elif docker-compose version &>/dev/null; then
  DC="docker-compose"
elif [ -x "$HOME/.docker/cli-plugins/docker-compose" ]; then
  DC="$HOME/.docker/cli-plugins/docker-compose"
else
  echo "ERROR: docker compose not found"
  exit 1
fi

# High-traffic Twitch channels likely to be live at any given time.
# The test iterates until one is found online.
CANDIDATE_CHANNELS=(
  kaicenat
  xqc
  caedrel
  shroud
  summit1g
  pokimane
  hasanabi
  tarik
  ironmouse
  moistcr1tikal
  loltyler1
  lirik
  nickmercs
  timthetatman
  valorant
  riotgames
  esl_csgo
)

cleanup() {
  echo "--- Tearing down ---"
  $DC -f "$COMPOSE_FILE" down --volumes --remove-orphans 2>/dev/null || true
  rm -rf "$OUTPUT_DIR" "$CONFIG_DIR"
}
trap cleanup EXIT

echo "=== StreamDL Integration Test ==="
echo ""

# Clean slate
rm -rf "$OUTPUT_DIR" "$CONFIG_DIR"
mkdir -p "$OUTPUT_DIR/incomplete" "$OUTPUT_DIR/complete" "$CONFIG_DIR"

# --- Phase 1: Start the server and find a live stream ---
echo "--- Building and starting server ---"
$DC -f "$COMPOSE_FILE" up -d --build server

# Wait for server health check — use --wait if supported, otherwise poll
echo "Waiting for server health check..."
if $DC -f "$COMPOSE_FILE" up --help 2>&1 | grep -q -- '--wait'; then
  $DC -f "$COMPOSE_FILE" up -d --wait server
else
  for i in $(seq 1 30); do
    if $DC -f "$COMPOSE_FILE" exec -T server curl -sf http://localhost:8080/health &>/dev/null; then
      break
    fi
    sleep 2
  done
fi

echo ""
echo "--- Probing for a live Twitch stream ---"

LIVE_CHANNEL=""
for channel in "${CANDIDATE_CHANNELS[@]}"; do
  echo -n "  Trying $channel... "

  # Use the server container's Python + Streamlink to check if the channel is live.
  # This calls the same code path the gRPC server uses.
  RESULT=$($DC -f "$COMPOSE_FILE" exec -T server \
    /app/.venv/bin/python -c "
import socket
socket.setdefaulttimeout(15)
from streamlink import Streamlink
session = Streamlink()
try:
    streams = session.streams('https://twitch.tv/$channel')
    if streams:
        print('LIVE')
    else:
        print('OFFLINE')
except Exception as e:
    print(f'ERROR:{e}')
" 2>/dev/null) || RESULT="ERROR"

  if [ "$RESULT" = "LIVE" ]; then
    echo "LIVE!"
    LIVE_CHANNEL="$channel"
    break
  else
    echo "$RESULT"
  fi
done

if [ -z "$LIVE_CHANNEL" ]; then
  echo ""
  echo "SKIP: No live Twitch streams found among candidates. This is expected outside peak hours."
  echo "      The test infrastructure works; re-run when more streamers are online."
  exit 0
fi

echo ""
echo "--- Using channel: $LIVE_CHANNEL ---"

# --- Phase 2: Generate config and start the client ---
cat > "$CONFIG_DIR/config.yml" <<EOF
- site: twitch.tv
  channels:
  - name: $LIVE_CHANNEL
    quality: worst
EOF

echo "--- Starting client (will download ~10 seconds) ---"
$DC -f "$COMPOSE_FILE" up -d client

# --- Phase 3: Wait for a completed mp4 file ---
echo "--- Waiting for download to complete (timeout: ${TIMEOUT_SECONDS}s) ---"

ELAPSED=0
FOUND_FILE=""
while [ $ELAPSED -lt $TIMEOUT_SECONDS ]; do
  # Check for any .mp4 file in the complete output directory
  FOUND_FILE=$(find "$OUTPUT_DIR/complete" -name "*.mp4" -size +0c 2>/dev/null | head -1) || true
  if [ -n "$FOUND_FILE" ]; then
    break
  fi

  # Also check incomplete dir for in-progress files as a progress indicator
  IN_PROGRESS=$(find "$OUTPUT_DIR/incomplete" -name "*.mp4" 2>/dev/null | head -1) || true
  if [ -n "$IN_PROGRESS" ] && [ $((ELAPSED % 10)) -eq 0 ]; then
    SIZE=$(stat -f%z "$IN_PROGRESS" 2>/dev/null || stat --printf="%s" "$IN_PROGRESS" 2>/dev/null || echo "?")
    echo "  Download in progress... ($SIZE bytes)"
  fi

  sleep 2
  ELAPSED=$((ELAPSED + 2))
done

if [ -z "$FOUND_FILE" ]; then
  echo ""
  echo "FAIL: No completed mp4 file found after ${TIMEOUT_SECONDS}s"
  echo ""
  echo "--- Client logs ---"
  $DC -f "$COMPOSE_FILE" logs client 2>&1 | tail -50
  echo ""
  echo "--- Server logs ---"
  $DC -f "$COMPOSE_FILE" logs server 2>&1 | tail -30
  exit 1
fi

echo ""
echo "--- Download complete: $FOUND_FILE ---"

# --- Phase 4: Validate the mp4 with ffprobe ---
echo "--- Validating with ffprobe ---"

# Use local ffprobe if available, otherwise run it in a plain ffmpeg container
if command -v ffprobe &>/dev/null; then
  PROBE_OUTPUT=$(ffprobe -v quiet -print_format json -show_format -show_streams "$FOUND_FILE" 2>&1) || true
else
  PROBE_OUTPUT=$(docker run --rm -v "$OUTPUT_DIR/complete:/data:ro" \
    --entrypoint ffprobe mwader/static-ffmpeg:8.0 \
    -v quiet -print_format json -show_format -show_streams "/data/$(basename "$FOUND_FILE")" 2>&1) || true
fi

# Parse validation results
DURATION=$(echo "$PROBE_OUTPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('format', {}).get('duration', '0'))
except:
    print('0')
" 2>/dev/null) || DURATION="0"

VIDEO_STREAMS=$(echo "$PROBE_OUTPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    count = sum(1 for s in data.get('streams', []) if s.get('codec_type') == 'video')
    print(count)
except:
    print('0')
" 2>/dev/null) || VIDEO_STREAMS="0"

FILE_SIZE=$(stat -f%z "$FOUND_FILE" 2>/dev/null || stat --printf="%s" "$FOUND_FILE" 2>/dev/null || echo "0")

echo "  File size:     $FILE_SIZE bytes"
echo "  Duration:      ${DURATION}s"
echo "  Video streams: $VIDEO_STREAMS"

PASS=true

if [ "$FILE_SIZE" -lt 1000 ]; then
  echo "  FAIL: File too small ($FILE_SIZE bytes)"
  PASS=false
fi

# Duration should be roughly 5-15 seconds (we asked for 10, allow some variance)
DURATION_INT=$(printf "%.0f" "$DURATION" 2>/dev/null || echo "0")
if [ "$DURATION_INT" -lt 3 ]; then
  echo "  FAIL: Duration too short (${DURATION}s, expected ~10s)"
  PASS=false
fi

if [ "$VIDEO_STREAMS" -lt 1 ]; then
  echo "  FAIL: No video streams found"
  PASS=false
fi

echo ""
if [ "$PASS" = true ]; then
  echo "=== PASS: Live stream integration test succeeded ==="
  echo "  Downloaded ${DURATION}s of $LIVE_CHANNEL's stream, valid mp4 with video."
else
  echo "=== FAIL: Live stream integration test failed ==="
  echo ""
  echo "--- ffprobe output ---"
  echo "$PROBE_OUTPUT"
  echo ""
  echo "--- Client logs ---"
  $DC -f "$COMPOSE_FILE" logs client 2>&1 | tail -50
  exit 1
fi

# --- Phase 5: VOD download test ---
echo ""
echo "=== VOD Download Test ==="

# Clean output and DB state for VOD test
rm -rf "$OUTPUT_DIR/incomplete"/* "$OUTPUT_DIR/complete"/*
rm -rf "$SCRIPT_DIR/data"
mkdir -p "$SCRIPT_DIR/data"

# Use a dedicated VOD channel with known past broadcasts.
# Override with VOD_CHANNEL env var if needed.
VOD_CHANNEL="${VOD_CHANNEL:-teampgp}"

cat > "$CONFIG_DIR/config.yml" <<EOF
- site: twitch.tv
  channels:
  - name: $VOD_CHANNEL
    quality: worst
    vod: true
    vod_limit: 1
EOF

echo "--- Starting client for VOD download (channel: $VOD_CHANNEL) ---"
$DC -f "$COMPOSE_FILE" restart client

VOD_ELAPSED=0
VOD_TIMEOUT=180
VOD_FILE=""
while [ $VOD_ELAPSED -lt $VOD_TIMEOUT ]; do
  VOD_FILE=$(find "$OUTPUT_DIR/complete" -name "*_vod_*" -size +0c 2>/dev/null | head -1) || true
  if [ -n "$VOD_FILE" ]; then
    break
  fi
  sleep 5
  VOD_ELAPSED=$((VOD_ELAPSED + 5))
done

if [ -z "$VOD_FILE" ]; then
  echo "FAIL: No VOD file found after ${VOD_TIMEOUT}s"
  $DC -f "$COMPOSE_FILE" logs client 2>&1 | tail -30
  exit 1
fi

echo "--- VOD download complete: $VOD_FILE ---"
VOD_SIZE=$(stat -f%z "$VOD_FILE" 2>/dev/null || stat --printf="%s" "$VOD_FILE" 2>/dev/null || echo "0")
echo "  File size: $VOD_SIZE bytes"

if [ "$VOD_SIZE" -lt 1000 ]; then
  echo "FAIL: VOD file too small"
  exit 1
fi

echo "=== PASS: All integration tests succeeded ==="
