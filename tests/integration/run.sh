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
FAILED=0

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

HOOKS_DIR="$SCRIPT_DIR/hooks"
LIVE_CHANNEL=""

cleanup() {
  echo "--- Tearing down ---"
  $DC -f "$COMPOSE_FILE" down --volumes --remove-orphans 2>/dev/null || true
  rm -rf "$OUTPUT_DIR" "$CONFIG_DIR" "$HOOKS_DIR"
}
trap cleanup EXIT

# Rebuild and recreate the client without restarting the server.
start_client() {
  $DC -f "$COMPOSE_FILE" up -d --build --force-recreate --no-deps client
}

assert_notice_after_wait() {
  local logs="$1"
  local channel="$2"
  printf '%s' "$logs" | python3 -c "
import sys
logs = sys.stdin.read()
wait_idx = logs.rfind('Waiting')
notice = '[${channel}]'
notice_idx = logs.rfind(notice)
if wait_idx == -1:
    print('wait line not found', file=sys.stderr)
    raise SystemExit(1)
if notice_idx == -1:
    print('notice not found for ${channel}', file=sys.stderr)
    raise SystemExit(1)
if notice_idx < wait_idx:
    print('notice appears before wait line', file=sys.stderr)
    raise SystemExit(1)
"
}

run_notice_tests() {
  echo ""
  echo "=== Tick Notice Buffer Tests ==="

  # Phase 6b: Kick (offline channel — deterministic)
  echo "--- Phase 6b: Kick offline notice ---"
  cat > "$CONFIG_DIR/config.yml" <<EOF
- site: kick.com
  channels:
  - name: nonexistent_user_12345
    quality: best
EOF

  export LOG_LEVEL=INFO
  start_client
  sleep 8

  KICK_LOGS=$($DC -f "$COMPOSE_FILE" logs client 2>&1)
  if assert_notice_after_wait "$KICK_LOGS" "nonexistent_user_12345"; then
    echo "  PASS: Kick offline notice appears after wait line"
  else
    echo "  FAIL: Kick offline notice not found in expected order"
    echo "$KICK_LOGS" | tail -40
    FAILED=1
  fi

  # Phase 6a: Twitch invalid quality (requires live channel from Phase 1)
  if [ -n "$LIVE_CHANNEL" ]; then
    echo "--- Phase 6a: Twitch invalid quality notice ---"
    cat > "$CONFIG_DIR/config.yml" <<EOF
- site: twitch.tv
  channels:
  - name: $LIVE_CHANNEL
    quality: this_quality_does_not_exist
EOF

    start_client
    sleep 8

    TWITCH_LOGS=$($DC -f "$COMPOSE_FILE" logs client 2>&1)
    if assert_notice_after_wait "$TWITCH_LOGS" "$LIVE_CHANNEL"; then
      echo "  PASS: Twitch quality notice appears after wait line"
    else
      echo "  FAIL: Twitch quality notice not found in expected order"
      echo "$TWITCH_LOGS" | tail -40
      FAILED=1
    fi
  else
    echo "SKIP: Phase 6a (no live Twitch channel from Phase 1)"
  fi
}

echo "=== StreamDL Integration Test ==="
echo ""

# Clean slate
rm -rf "$OUTPUT_DIR" "$CONFIG_DIR" "$HOOKS_DIR"
mkdir -p "$OUTPUT_DIR/incomplete" "$OUTPUT_DIR/complete" "$OUTPUT_DIR/hook-markers" "$CONFIG_DIR" "$HOOKS_DIR"

# Create post-download hook script that writes a marker file with context
cat > "$HOOKS_DIR/post_hook.sh" <<'HOOKEOF'
#!/bin/sh
echo "${STREAMDL_TYPE}|${STREAMDL_USER}|${STREAMDL_SITE}|${STREAMDL_FILE}" > "/app/hook-markers/${STREAMDL_TYPE}_${STREAMDL_USER}.txt"
HOOKEOF
chmod +x "$HOOKS_DIR/post_hook.sh"

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
  echo "      Continuing with notice buffer tests only."
  run_notice_tests
  if [ "$FAILED" -ne 0 ]; then
    exit 1
  fi
  echo "=== PASS: Notice buffer tests succeeded (live/VOD phases skipped) ==="
  exit 0
fi

echo ""
echo "--- Using channel: $LIVE_CHANNEL ---"

# --- Phase 2: Generate config and start the client ---
cat > "$CONFIG_DIR/config.yml" <<EOF
- site: twitch.tv
  post_script: /app/hooks/post_hook.sh
  channels:
  - name: $LIVE_CHANNEL
    quality: worst
EOF

echo "--- Starting client (will download ~10 seconds) ---"
start_client

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
  FAILED=1
else
  echo ""
  echo "--- Download complete: $FOUND_FILE ---"

  # --- Phase 4: Validate the mp4 with ffprobe ---
  echo "--- Validating with ffprobe ---"

  # Use local ffprobe if available, otherwise run it in a plain ffmpeg container
  if command -v ffprobe &>/dev/null; then
    PROBE_OUTPUT=$(ffprobe -v quiet -print_format json -show_format -show_streams "$FOUND_FILE" 2>&1) || true
  else
    PROBE_OUTPUT=$(docker run --rm -v "$OUTPUT_DIR/complete:/data:ro" \
      --entrypoint ffprobe mwader/static-ffmpeg:8.1 \
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
    FAILED=1
  fi

  # --- Phase 4b: Verify post_script hook fired for live stream ---
  echo ""
  echo "--- Checking post_script hook marker (live) ---"
  LIVE_MARKER="$OUTPUT_DIR/hook-markers/live_${LIVE_CHANNEL}.txt"
  if [ -f "$LIVE_MARKER" ]; then
    MARKER_CONTENT=$(cat "$LIVE_MARKER")
    echo "  Hook fired! Marker: $MARKER_CONTENT"
    if echo "$MARKER_CONTENT" | grep -q "^live|${LIVE_CHANNEL}|twitch.tv|"; then
      echo "  PASS: post_script hook ran with correct context"
    else
      echo "  WARN: Hook marker exists but content unexpected: $MARKER_CONTENT"
    fi
  else
    echo "  WARN: post_script hook marker not found (script may not have finished yet)"
    echo "  This is non-fatal — the hook runs asynchronously after file move"
  fi
fi

# --- Phase 5: VOD download test (non-fatal — notice tests always run after) ---
echo ""
echo "=== VOD Download Test ==="

# Clean output and DB state for VOD test
rm -rf "$OUTPUT_DIR/incomplete"/* "$OUTPUT_DIR/complete"/*
rm -rf "$SCRIPT_DIR/data"
mkdir -p "$SCRIPT_DIR/data"

# Channels known to have VODs, in priority order.
# Override with VOD_CHANNEL env var to skip probing.
CANDIDATE_VOD_CHANNELS=(
  teampgp
  kaicenat
  xqc
  hasanabi
  shroud
  summit1g
)

VOD_CHANNEL="${VOD_CHANNEL:-}"
ANY_PROBE_OK=false

if [ -n "$VOD_CHANNEL" ]; then
  echo "--- Using VOD_CHANNEL override: $VOD_CHANNEL ---"
else
  echo "--- Probing for a channel with VODs ---"
  for vod_candidate in "${CANDIDATE_VOD_CHANNELS[@]}"; do
    echo -n "  Trying $vod_candidate... "
    RESULT=$($DC -f "$COMPOSE_FILE" exec -T server \
      /app/.venv/bin/python -c "
import socket
socket.setdefaulttimeout(15)
import yt_dlp
try:
    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True, 'extract_flat': 'in_playlist', 'playlistend': 1}) as ydl:
        info = ydl.extract_info('https://twitch.tv/$vod_candidate/videos', download=False)
        if info and 'entries' in info and list(info['entries']):
            print('HAS_VODS')
        else:
            print('NO_VODS')
except Exception as e:
    print(f'ERROR:{e}')
" 2>/dev/null) || RESULT="ERROR"

    if [ "$RESULT" = "HAS_VODS" ]; then
      echo "has VODs!"
      VOD_CHANNEL="$vod_candidate"
      break
    else
      echo "$RESULT"
      if [ "$RESULT" = "NO_VODS" ]; then
        ANY_PROBE_OK=true
      fi
    fi
  done
fi

if [ -z "$VOD_CHANNEL" ]; then
  if [ "$ANY_PROBE_OK" = false ]; then
    echo ""
    echo "WARN: All VOD probes failed with errors. Skipping VOD phase."
    echo "--- Server logs ---"
    $DC -f "$COMPOSE_FILE" logs server 2>&1 | tail -30
  else
    echo ""
    echo "SKIP: No channels with VODs found among candidates."
  fi
else
  cat > "$CONFIG_DIR/config.yml" <<EOF
- site: twitch.tv
  post_script: /app/hooks/post_hook.sh
  channels:
  - name: $VOD_CHANNEL
    quality: worst
    vod: true
    vod_limit: 1
EOF

  echo "--- Starting client for VOD download (channel: $VOD_CHANNEL) ---"
  start_client

  VOD_ELAPSED=0
  VOD_TIMEOUT="${VOD_TIMEOUT:-180}"
  VOD_FILE=""
  VOD_PROGRESS=""
  while [ "$VOD_ELAPSED" -lt "$VOD_TIMEOUT" ]; do
    VOD_FILE=$(find "$OUTPUT_DIR/complete" -name "*_vod_*.mp4" -size +0c 2>/dev/null | head -1) || true
    if [ -n "$VOD_FILE" ]; then
      break
    fi
    VOD_PROGRESS=$(find "$OUTPUT_DIR/incomplete" -name "*_vod_*.mp4" -size +1000c 2>/dev/null | head -1) || true
    if [ -n "$VOD_PROGRESS" ]; then
      echo "--- VOD download in progress: $VOD_PROGRESS ---"
      break
    fi
    sleep 5
    VOD_ELAPSED=$((VOD_ELAPSED + 5))
  done

  if [ -z "$VOD_FILE" ] && [ -z "$VOD_PROGRESS" ]; then
    echo "WARN: No VOD download activity found after ${VOD_TIMEOUT}s"
    echo ""
    echo "--- Client logs ---"
    $DC -f "$COMPOSE_FILE" logs client 2>&1 | tail -30
    echo ""
    echo "--- Server logs ---"
    $DC -f "$COMPOSE_FILE" logs server 2>&1 | tail -30
    FAILED=1
  else
    if [ -n "$VOD_FILE" ]; then
      echo "--- VOD download complete: $VOD_FILE ---"
      VOD_CHECK="$VOD_FILE"
    else
      echo "--- VOD download started (in progress): $VOD_PROGRESS ---"
      VOD_CHECK="$VOD_PROGRESS"
    fi

    VOD_SIZE=$(stat -f%z "$VOD_CHECK" 2>/dev/null || stat --printf="%s" "$VOD_CHECK" 2>/dev/null || echo "0")
    echo "  File size: $VOD_SIZE bytes"

    if [ "$VOD_SIZE" -lt 1000 ]; then
      echo "WARN: VOD file too small"
      FAILED=1
    else
      echo "--- Checking post_script hook marker (vod) ---"
      VOD_MARKER="$OUTPUT_DIR/hook-markers/vod_${VOD_CHANNEL}.txt"
      if [ -n "$VOD_FILE" ] && [ -f "$VOD_MARKER" ]; then
        MARKER_CONTENT=$(cat "$VOD_MARKER")
        echo "  Hook fired! Marker: $MARKER_CONTENT"
        if echo "$MARKER_CONTENT" | grep -q "^vod|${VOD_CHANNEL}|twitch.tv|"; then
          echo "  PASS: post_script hook ran with correct context"
        else
          echo "  WARN: Hook marker exists but content unexpected: $MARKER_CONTENT"
        fi
      elif [ -n "$VOD_PROGRESS" ]; then
        echo "  SKIP: VOD still in progress, hook fires after completion"
      else
        echo "  WARN: VOD hook marker not found"
      fi
    fi
  fi
fi

run_notice_tests

if [ "$FAILED" -ne 0 ]; then
  echo "=== FAIL: One or more integration test phases failed ==="
  exit 1
fi

echo "=== PASS: All integration tests succeeded ==="
