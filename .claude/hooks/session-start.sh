#!/bin/bash
# Cloud session setup for ck2-mods. The repo's tools need only the Python
# standard library; this hook makes the CK2 reference material available.
# Every step is best effort: a missing network or file never fails the session.
#
#   .cwtools/        CWTools rules for CK2 (git submodule): machine-readable
#                    syntax for effects, triggers, scopes, modifiers
#   reference/emf/   EMF mod source (gitignored), working script examples
#   vanilla/         the game's own files (gitignored), unpacked from the copy
#                    stored in the Claude project's shared files, if present
set -uo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}" || exit 0
say() { echo "session-start: $*"; }

if [ ! -f .cwtools/effects.cwt ]; then
  if git submodule update --init --depth 1 .cwtools >/dev/null 2>&1; then
    say "fetched CWTools rules into .cwtools/"
  else
    say "could not fetch .cwtools/ (network?)"
  fi
fi

if [ ! -d reference/emf/.git ]; then
  mkdir -p reference
  if git clone -q --depth 1 https://github.com/EMFTeam/EMF reference/emf 2>/dev/null; then
    say "cloned EMF into reference/emf/"
  else
    rm -rf reference/emf
    say "could not clone EMF (network?)"
  fi
fi

zip="${CK2_VANILLA_ZIP:-/mnt/project-files/ck2-vanilla/ck2-game-files.zip}"
stamp=vanilla/.source.sha256
if [ -f "$zip" ]; then
  want="$(sha256sum "$zip" | cut -d' ' -f1)"
  if [ "$(cat "$stamp" 2>/dev/null || true)" != "$want" ]; then
    if tools/fetch_vanilla.sh "$zip" >/dev/null; then
      echo "$want" > "$stamp"
      say "unpacked game files into vanilla/"
    else
      say "failed to unpack $zip"
    fi
  fi
elif [ ! -d vanilla ]; then
  say "no game files at $zip; use .cwtools/ and reference/emf/ for syntax"
fi

if command -v cwtools >/dev/null 2>&1; then
  say "cwtools CLI available"
fi
exit 0
