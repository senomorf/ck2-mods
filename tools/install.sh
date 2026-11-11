#!/usr/bin/env bash
# Link a mod from this repo into the CK2 user mod folder (Linux/macOS).
# Usage: tools/install.sh <mod_folder> [ck2_user_dir]
# Default user dir is a guess; pass yours if the game uses another path.
set -euo pipefail
mod="${1:?usage: tools/install.sh <mod_folder> [ck2_user_dir]}"
repo="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -n "${2:-}" ]]; then
  user_dir="$2"
elif [[ "$(uname)" == "Darwin" ]]; then
  user_dir="$HOME/Documents/Paradox Interactive/Crusader Kings II"
else
  user_dir="$HOME/.paradoxinteractive/Crusader Kings II"
fi
[[ -d "$repo/mods/$mod" ]] || { echo "no mods/$mod in repo" >&2; exit 1; }
[[ -d "$user_dir" ]] || { echo "CK2 user dir not found: $user_dir (pass it as 2nd argument)" >&2; exit 1; }
mkdir -p "$user_dir/mod"
ln -sfn "$repo/mods/$mod" "$user_dir/mod/$mod"
cp "$repo/mods/$mod.mod" "$user_dir/mod/$mod.mod"
echo "linked $user_dir/mod/$mod -> $repo/mods/$mod"
echo "copied $mod.mod (re-run after changing the descriptor)"
