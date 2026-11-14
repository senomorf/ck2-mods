#!/usr/bin/env bash
# Smoke-test mods on Linux: boot CK2 headless (Xvfb, Mesa's software OpenGL) with each mod, wait
# for the main menu, and fail on error.log lines a vanilla boot does not have. The Linux twin of
# tools/smoke.ps1, for the `linux smoke` job (docs/test-pipeline.md).
#
# Usage: tools/smoke.sh [mod...]      no mod named: every mod under mods/ but _template
#
# Env: CK2_GAME_DIR   game folder (default /game, the runner's read-only mount)
#      CK2_USER_DIR   CK2 user folder (default ~/.paradoxinteractive/Crusader Kings II)
#      SMOKE_OUT      reports (default smoke-reports/ in the repo): <name>/report.txt and the logs
#      SMOKE_TIMEOUT  seconds a boot may take (default 300)
#      SMOKE_SETTLE   seconds to keep running after the menu is up (default 15)
#      SMOKE_LABEL_WAIT  seconds to wait for the main menu's version label (default 90)
#
# Measured on the fleet runner (senomorf/homelab#2322, 2026-11-13), CK2 3.3.5.1:
# - booted = game.log gains "After first history execution", the same line the Windows build
#   writes; a boot took 20 to 30 s under llvmpipe (70 s once, with the host busy).
# - an empty user folder stops at a "Choose language" dialog and waits for a click; settings.txt
#   with gui = { language=l_english has_set_language=yes } skips it (`language="l_english"` alone
#   does not).
# - there is no Steam client: "SteamAPI_Init() failed" is logged and the game carries on, but only
#   without a network. With one it prints "Please start Crusader Kings II through steam for your
#   first time start-up" and exits 1 at about 16 s. So the game runs in a network namespace of its
#   own (unshare -rn: only a downed loopback), and the job keeps its network for GitHub.
# Every run boots vanilla first: an ephemeral runner keeps no baseline between jobs.
#
# Multiplayer checksum: the main menu's bottom-left label shows the version and the checksum code
# multiplayer compares, "3.3.5.1 (SOHY)" for vanilla and "3.3.5.1 (TENS)" with allied_fleets' test
# copy (live test box, 2026-11-13). The game writes the code to no log, and a save's checksum= line
# changes with the game's state, so the script compares the label's pixels: each boot saves the
# label as version.png, and a mod whose label differs from vanilla's changes the checksum (label
# the pull request mp-checksum). Needs xwd, xwdtopnm and pnmtopng; without them it is skipped.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
game=${CK2_GAME_DIR:-/game}
ud=${CK2_USER_DIR:-$HOME/.paradoxinteractive/Crusader Kings II}
out=${SMOKE_OUT:-$repo/smoke-reports}
limit=${SMOKE_TIMEOUT:-300} settle=${SMOKE_SETTLE:-15}

[ -x "$game/ck2" ] || { echo "smoke: no executable ck2 in $game (set CK2_GAME_DIR)" >&2; exit 2; }
command -v Xvfb >/dev/null || { echo "smoke: Xvfb is not installed" >&2; exit 2; }
if [ "$#" -gt 0 ]; then
  mods=("$@")
else
  mods=()
  for d in "$repo"/mods/*/; do d=${d%/}; d=${d##*/}; [[ $d == _* ]] || mods+=("$d"); done
fi
for m in "${mods[@]}"; do
  [ -d "$repo/mods/$m" ] && [ -f "$repo/mods/$m.mod" ] || { echo "smoke: no mods/$m with mods/$m.mod" >&2; exit 2; }
done
if pgrep -x ck2 >/dev/null; then echo "smoke: ck2 is already running" >&2; exit 2; fi
unshare -rn true 2>/dev/null || { echo "smoke: cannot give the game a network namespace (unshare -rn)" >&2; exit 2; }

export DISPLAY=:${SMOKE_DISPLAY:-99} SDL_AUDIODRIVER=${SDL_AUDIODRIVER:-dummy} LIBGL_ALWAYS_SOFTWARE=1
# -noreset: by default Xvfb resets when its last client disconnects, and a connection made during
# the reset fails. A boot then dies at once with "Failed to initialize SDL! SDL_Error: No available
# video device" (seen once, 2026-11-13, on the boot right after the baseline's).
Xvfb "$DISPLAY" -screen 0 1280x720x24 -nolisten tcp -noreset >/dev/null 2>&1 &
xvfb=$!
pid=
cleanup() { [ -z "$pid" ] || kill -9 "$pid" 2>/dev/null || true; kill "$xvfb" 2>/dev/null || true; }
trap cleanup EXIT
sleep 2
kill -0 "$xvfb" 2>/dev/null || { echo "smoke: Xvfb did not start on $DISPLAY" >&2; exit 2; }

mkdir -p "$ud/mod" "$out"
# look DEST: the screen's version label: writes DEST/version.ppm and prints the hash of its text
# area and how many bright pixels it has (263 on vanilla's label, at most 93 on the loading and
# game screens of the box probes, 2026-11-13). The text is centred, so a different code also moves
# the version digits.
look() {
  xwd -root -display "$DISPLAY" 2>/dev/null | xwdtopnm 2>/dev/null | python3 -I -c '
import hashlib, sys
d = sys.stdin.buffer.read()
f, i = [], 0
while len(f) < 4:
    while d[i:i + 1].isspace():
        i += 1
    if d[i:i + 1] == b"#":
        i = d.index(b"\n", i) + 1
        continue
    j = i
    while not d[j:j + 1].isspace():
        j += 1
    f.append(d[i:j])
    i = j
w, px = int(f[1]), d[i + 1:]
if f[0] != b"P6" or f[3] != b"255":
    sys.exit(1)
def crop(x, y, cw, ch):
    return b"".join(px[((y + r) * w + x) * 3:((y + r) * w + x + cw) * 3] for r in range(ch))
text = crop(26, 672, 132, 22)
bright = sum(1 for k in range(0, len(text), 3) if sum(text[k:k + 3]) > 450)
open(sys.argv[1], "wb").write(b"P6\n144 36\n255\n" + crop(20, 664, 144, 36))
print(hashlib.md5(text).hexdigest()[:12], bright)
' "$1/version.ppm" 2>/dev/null || true
}
# read_label DEST: wait for the version label and set $code to its hash ('' when not read): the
# label counts once its text area is bright and looks the same five times 2 s apart, since the
# menu can still be loading when the boot counts as done.
code=''
read_label() {
  local dest=$1 t0=$SECONDS t h b last='' same=0
  code=''
  for t in xwd xwdtopnm pnmtopng; do command -v "$t" >/dev/null || return 0; done
  while [ $((SECONDS - t0)) -lt "${SMOKE_LABEL_WAIT:-90}" ]; do
    read -r h b <<< "$(look "$dest")" || true
    if [ "${b:-0}" -ge 150 ] && [ "${h:-}" = "$last" ]; then
      same=$((same + 1))
      if [ "$same" -ge 4 ]; then code=$h; break; fi
    else
      same=0
    fi
    last=${h:-}
    sleep 2
  done
  if [ -n "$code" ]; then pnmtopng "$dest/version.ppm" > "$dest/version.png" 2>/dev/null || true; fi
  rm -f "$dest/version.ppm"
}
# Lines compared without their leading [file:line]: tags, which move between game builds.
norm() { sed -E 's/\r$//; s/^(\[[^]]*\])+[[:space:]]*:?[[:space:]]*//; s/[[:space:]]+$//' "$@" | grep -v '^$' || true; }

# boot NAME [game args...]: boots once; sets $status and $secs, leaves the logs in $out/NAME.
boot() {
  local name=$1; shift
  local dest="$out/$name" start=$SECONDS booted='' i
  rm -rf "$dest" "$ud/logs"; mkdir -p "$dest"
  grep -qs has_set_language "$ud/settings.txt" \
    || printf 'gui=\n{\n\tlanguage=l_english\n\thas_set_language=yes\n}\n' > "$ud/settings.txt"
  (cd "$game" && LD_LIBRARY_PATH="$game${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" exec unshare -rn ./ck2 -skiplauncher -debugscripts "$@") \
    > "$dest/stdout.log" 2>&1 &
  pid=$! status=timeout
  while :; do
    sleep 2
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid" && i=0 || i=$?
      status="exited early (code $i)"; pid=; break
    fi
    if [ -z "$booted" ] && grep -qs 'After first history execution' "$ud/logs/game.log"; then booted=$((SECONDS - start)); fi
    if [ -n "$booted" ] && [ $((SECONDS - start)) -ge $((booted + settle)) ]; then status=booted; break; fi
    [ $((SECONDS - start)) -lt "$limit" ] || break
  done
  secs=${booted:-$((SECONDS - start))}
  if [ "$status" = booted ]; then read_label "$dest"; else code=''; fi
  if [ "$status" != booted ] && command -v xwd >/dev/null; then
    xwd -root -display "$DISPLAY" 2>/dev/null | xwdtopnm 2>/dev/null | pnmtopng > "$dest/screen.png" 2>/dev/null || rm -f "$dest/screen.png"
  fi
  if [ -n "$pid" ]; then
    kill "$pid" 2>/dev/null || true
    for i in 1 2 3 4 5; do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -9 "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; pid=
  fi
  cp "$ud"/logs/*.log "$dest/" 2>/dev/null || true
}

boot _baseline
echo "baseline: $status after ${secs}s"
vanilla_code=$code
if [ -n "$vanilla_code" ]; then echo "baseline: version label $vanilla_code ($out/_baseline/version.png)"; else echo "baseline: version label not read"; fi
[ "$status" = booted ] || { echo "smoke: vanilla did not boot ($status); see $out/_baseline" >&2; exit 1; }
norm "$out/_baseline/error.log" 2>/dev/null | sort -u > "$out/_baseline/error.norm"

failed=()
for m in "${mods[@]}"; do
  "$repo/tools/install.sh" "$m" "$ud" >/dev/null
  boot "$m" "-mod=mod/$m.mod"
  if [ -z "$vanilla_code" ] || [ -z "$code" ]; then
    mp="not read (no version label in vanilla's or this boot)"
  elif [ "$code" = "$vanilla_code" ]; then
    mp="same as vanilla's ($code)"
  else
    mp="$code, differs from vanilla's $vanilla_code: players need this mod's same version; label the pull request mp-checksum"
    echo "::warning title=multiplayer checksum::$m changes the multiplayer checksum (main menu label)"
  fi
  rm -f "$ud/mod/$m" "$ud/mod/$m.mod"
  dest="$out/$m"
  norm "$dest/error.log" 2>/dev/null | grep -vxF -f "$out/_baseline/error.norm" | sort | uniq -c | sort -rn > "$dest/new-errors.txt" || true
  n=$(grep -c . "$dest/new-errors.txt" || true)
  # system.log names mod/<folder> when the game loads it, and a vanilla boot does not, so a mod
  # that never loaded cannot pass with no errors.
  seen=false
  if grep -aqsF "mod/$m" "$dest/system.log"; then seen=true; fi
  {
    echo "CK2 smoke test: $m"
    echo "result: $status after ${secs}s; args: -skiplauncher -debugscripts -mod=mod/$m.mod"
    echo "mod named in logs: $seen"
    echo "new error.log lines vs baseline: $n"
    echo "multiplayer checksum (main menu label; _baseline/version.png and $m/version.png): $mp"
    cat "$dest/new-errors.txt"
  } > "$dest/report.txt"
  cat "$dest/report.txt"
  if [ "$status" != booted ] || [ "$n" -gt 0 ] || [ "$seen" != true ]; then failed+=("$m"); fi
done
[ "${#failed[@]}" -eq 0 ] || { echo "failed: ${failed[*]}"; exit 1; }
echo "all mods clean: ${mods[*]}"
