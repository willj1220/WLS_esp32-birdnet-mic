#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/web-flasher"
REMOTE_HOST="${REMOTE_HOST:-rpi5}"
REMOTE_DIR="${REMOTE_DIR:-/home/msrpi/web-projects/web-flasher}"
REMOTE="$REMOTE_HOST:$REMOTE_DIR/"
PUBLIC_URL="${PUBLIC_URL:-https://esp32mic.msmeteo.cz}"
PUBLIC_FW_URL="${PUBLIC_FW_URL:-http://esp32mic.msmeteo.cz/firmware-app.bin}"
LOCAL_URL="${LOCAL_URL:-http://127.0.0.1:8083}"

usage() {
  cat <<EOF
Usage: $0

Deploys web-flasher/ to $REMOTE_HOST:$REMOTE_DIR and verifies $PUBLIC_URL.

Environment overrides:
  REMOTE_HOST  default: rpi5
  REMOTE_DIR   default: /home/msrpi/web-projects/web-flasher
  LOCAL_URL    default: http://127.0.0.1:8083
  PUBLIC_URL   default: https://esp32mic.msmeteo.cz
  PUBLIC_FW_URL default: http://esp32mic.msmeteo.cz/firmware-app.bin
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "$#" -gt 0 ]]; then
  usage >&2
  exit 2
fi

trap 'echo "Deploy failed at line $LINENO: $BASH_COMMAND" >&2' ERR

log() {
  printf '\n== %s ==\n' "$*"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

validate_web_files() {
  local required=(
    README.md
    index.html
    manifest.json
    bird.png
    bootloader.bin
    partitions.bin
    boot_app0.bin
    firmware.bin
    firmware-app.bin
    ota-version.txt
  )

  for file in "${required[@]}"; do
    if [[ ! -s "$WEB_DIR/$file" ]]; then
      echo "Missing or empty web flasher file: $WEB_DIR/$file" >&2
      exit 1
    fi
  done

  python3 -m json.tool "$WEB_DIR/manifest.json" >/dev/null

  python3 - "$WEB_DIR" <<'PY'
import json
import pathlib
import sys

web_dir = pathlib.Path(sys.argv[1])
manifest = json.loads((web_dir / "manifest.json").read_text(encoding="utf-8"))
missing = []
for build in manifest.get("builds", []):
    for part in build.get("parts", []):
        path = web_dir / part.get("path", "")
        if not path.exists() or path.stat().st_size == 0:
            missing.append(str(path))
if missing:
    raise SystemExit("Missing firmware files referenced by manifest:\n" + "\n".join(missing))
PY
}

log "Checking local tooling"
require_command python3
require_command rsync
require_command ssh
require_command curl
require_command grep

log "Validating local web flasher files"
validate_web_files

log "Checking remote target"
ssh "$REMOTE_HOST" "test -d '$REMOTE_DIR'"

log "Syncing web flasher to $REMOTE_HOST:$REMOTE_DIR"
rsync_opts=(
  -a
  --delete
  --human-readable
  --itemize-changes
  --exclude '.git/'
  --exclude '*.bak-*'
)
rsync "${rsync_opts[@]}" "$WEB_DIR/" "$REMOTE"

log "Verifying RPI endpoint"
ssh "$REMOTE_HOST" "curl -fsS '$LOCAL_URL/manifest.json' | python3 -m json.tool >/dev/null"
ssh "$REMOTE_HOST" "html=\$(curl -fsS '$LOCAL_URL/') && grep -q 'esp-web-install-button' <<<\"\$html\""

log "Verifying public endpoint"
curl -fsS "$PUBLIC_URL/manifest.json" | python3 -m json.tool >/dev/null
public_html="$(curl -fsS "$PUBLIC_URL/")"
grep -q 'esp-web-install-button' <<<"$public_html"
fw_headers="$(curl -fsSI "$PUBLIC_FW_URL" | tr -d '\r')"
grep -Eiq '^content-type: (application/octet-stream|application/macbinary|binary/octet-stream)' <<<"$fw_headers"
local_fw_size="$(stat -c '%s' "$WEB_DIR/firmware-app.bin")"
public_fw_size="$(awk 'tolower($1)=="content-length:" {print $2; exit}' <<<"$fw_headers")"
if [[ "$public_fw_size" != "$local_fw_size" ]]; then
  echo "Public firmware size mismatch: got ${public_fw_size:-unknown}, expected $local_fw_size from $PUBLIC_FW_URL" >&2
  exit 1
fi

echo "Deployed and verified $PUBLIC_URL"
