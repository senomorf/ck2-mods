#!/usr/bin/env bash
# Run a command on the live CK2 test box against this working tree, then copy its reports back.
# Needs the `ssh ck2box` alias from tools/box-connect.sh; the first ssh command starts the box.
#
# Usage: tools/box-run.sh COMMAND [ARG...]
#   tools/box-run.sh tools/campaign.sh allied_fleets
#   tools/box-run.sh env CAMPAIGN_PROBE_SAVE=.box/start.ck2 CAMPAIGN_PROBE_EFFECTS=.box/fx.txt \
#     CAMPAIGN_PROBE_MOD=allied_fleets tools/campaign.sh --steps tools/campaign/run_effects.txt
#
# Copies tools/, mods/ and tests/ as they are in the working tree (committed or not), plus .box/
# (gitignored: saves and scratch files for the box), to ~/ck2-mods on the box, replacing the last
# copy. Afterwards campaign-reports/ and smoke-reports/ come back into this checkout.
# `ssh ck2box box-stop` when done: the box shares the CI runner's memory.
# shellcheck disable=SC2029 # the remote commands are built here on purpose
set -euo pipefail
[ "$#" -gt 0 ] || { sed -n '2,13p' "$0" >&2; exit 2; }
repo=$(cd "$(dirname "$0")/.." && pwd)
cd "$repo"
{
  git ls-files -z --cached --others --exclude-standard -- tools mods tests
  [ ! -d .box ] || find .box -type f -print0
} | tar --null -T - -cf - | ssh ck2box 'rm -rf ck2-mods && mkdir ck2-mods && tar -xf - -C ck2-mods'
status=0
ssh ck2box "cd ck2-mods && $(printf '%q ' "$@")" || status=$?
for d in campaign-reports smoke-reports; do
  if ssh ck2box "test -d ck2-mods/$d"; then
    rm -rf "${repo:?}/$d"
    ssh ck2box "tar -C ck2-mods -cf - $d" | tar -xf -
  fi
done
exit "$status"
