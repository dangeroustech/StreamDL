#!/bin/sh
# Manual test hook for post_script feature.
# Add this to your config as post_script and watch the marker file.
#
# Usage:
#   1. Copy this script somewhere accessible to StreamDL (e.g. /app/hooks/test_hook.sh)
#   2. Make it executable: chmod +x /app/hooks/test_hook.sh
#   3. Add to your config.yml:
#        - site: twitch.tv
#          post_script: /app/hooks/test_hook.sh
#          channels:
#          - name: <streamer>
#            quality: best
#   4. Wait for the streamer to end their stream (or start/stop one)
#   5. Check /tmp/streamdl_hook_log.txt for output
#
# The script logs all context it receives so you can verify everything works.

LOGFILE="/tmp/streamdl_hook_log.txt"

echo "========================================" >> "$LOGFILE"
echo "post_script fired at: $(date)" >> "$LOGFILE"
echo "  File:  $STREAMDL_FILE" >> "$LOGFILE"
echo "  User:  $STREAMDL_USER" >> "$LOGFILE"
echo "  Site:  $STREAMDL_SITE" >> "$LOGFILE"
echo "  Type:  $STREAMDL_TYPE" >> "$LOGFILE"
echo "  \$1:    $1" >> "$LOGFILE"
echo "========================================" >> "$LOGFILE"
