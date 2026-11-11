#!/usr/bin/env bash
# Unpack a zip of the game's own files into vanilla/ (gitignored) for reference and lint.
# Usage: tools/fetch_vanilla.sh <path/to/ck2-game-files.zip>
# Never commit vanilla/: it is Paradox's content.
set -euo pipefail
zip="${1:?usage: tools/fetch_vanilla.sh <zip>}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
python3 -I -c 'import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])' "$zip" "$tmp"
# Accept zips with or without a top-level folder.
src="$tmp"
entries=("$tmp"/*)
if [[ ${#entries[@]} -eq 1 && -d "${entries[0]}" && ! -d "$tmp/common" ]]; then src="${entries[0]}"; fi
rm -rf "$repo/vanilla"
mv "$src" "$repo/vanilla"
[[ "$src" == "$tmp" ]] && trap - EXIT
echo "vanilla/ now holds: $(find "$repo/vanilla" -mindepth 1 -maxdepth 1 -printf '%f ')"
