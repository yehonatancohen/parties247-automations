#!/bin/bash
# Run locally in Git Bash:  bash projects/video_creator/deploy/push-env.sh
# Copies TELEGRAM_TOKEN, ALLOWED_USER_ID and GEMINI_API_KEY from the local .env.test into the
# VPS deploy .env. Values travel over the ssh pipe only and are never printed.
set -e
SRC="$(cd "$(dirname "$0")/../../.." && pwd)/.env.test"
[ -f "$SRC" ] || { echo "missing $SRC"; exit 1; }

REMOTE='cd /home/ubuntu/video-mcp/projects/video_creator/deploy
while IFS= read -r line; do
  k=${line%%=*}; v=${line#*=}; v=${v%\"}; v=${v#\"}
  sed -i "s|^$k=.*|$k=$v|" .env
done
sed -E "s/(SECRET=|TOKEN=|KEY=|USER_ID=)(.+)/\1<set>/" .env'
B64=$(printf '%s' "$REMOTE" | base64 -w0)

grep -E '^(TELEGRAM_TOKEN|ALLOWED_USER_ID|GEMINI_API_KEY)=' "$SRC" | tr -d '\r' | \
  wsl.exe -d Ubuntu -u root -- bash -lc "ssh -i /root/ssh-key-2026-01-29.key ubuntu@130.110.238.248 'echo $B64 | base64 -d > /tmp/pe.sh; bash /tmp/pe.sh; rm -f /tmp/pe.sh'" 2>&1 \
  | grep -v "Failed to translate\|^nslate\|^anslate"
