#!/bin/bash
# Cloud session setup for ck2-mods. Tools use only the Python standard library,
# so the one job here is making vanilla/ (the game's files, never committed)
# available from the copy stored in the Claude project's shared files.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

zip="${CK2_VANILLA_ZIP:-/mnt/project-files/ck2-vanilla/ck2-game-files.zip}"
stamp=vanilla/.source.sha256

if [ -f "$zip" ]; then
  want="$(sha256sum "$zip" | cut -d' ' -f1)"
  if [ "$(cat "$stamp" 2>/dev/null || true)" != "$want" ]; then
    tools/fetch_vanilla.sh "$zip" >/dev/null
    echo "$want" > "$stamp"
    echo "session-start: unpacked game files into vanilla/"
  fi
else
  echo "session-start: no game files at $zip; vanilla/ lookups and vanilla localisation checks unavailable"
fi
