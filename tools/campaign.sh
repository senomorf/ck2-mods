#!/usr/bin/env bash
# Runtime smoke (roadmap #13, step 2): run CK2 for an in-game year with each mod and fail on new
# error.log lines that name the mod. The game runs headless (Xvfb, Mesa's software OpenGL) and is
# driven through its menus with xdotool clicks from steps files, with a screenshot at each `shot`.
#
# Usage: tools/campaign.sh [mod...]      no mod named: every mod under mods/ but _template
#        tools/campaign.sh --steps FILE  probe: boot vanilla, follow one steps file, keep everything
#
# Flow:
#  1. vanilla: start a new game through the menus (tools/campaign/new_game.txt), run it at full
#     speed to the first yearly autosave (CAMPAIGN_START), keep that save, run on to CAMPAIGN_END.
#  2. each mod: put that save back as the only one, boot with the mod straight into it
#     (tools/campaign/continue.txt), run to CAMPAIGN_END. So each mod plays the same year as
#     vanilla did, from a save made without it: this also checks that existing saves load.
#     With CAMPAIGN_BASE (a git commit) naming a version of the mod that this one changes, that
#     version plays the year first, and this version loads its save and plays the next year:
#     a save made with the old version must load with the new one.
#     The mod is installed as a copy by tools/harness.py, which logs each of its events as it fires
#     and adds the mod's in-game tests from tests/game/<mod>/, if any.
#  3. report the mod run's error.log lines that vanilla's run does not have. Lines that name the
#     mod (its prefix, folder or one of its file names) fail the run; the rest are listed as
#     warnings, since the game's own runtime errors differ from run to run. Then the harness's
#     report (harness.txt): a failed test, unfinished tests, or, for a mod with tests, an event that
#     never fired fail the run too. Then the run's last save, read by tools/ck2save.py: the checks
#     in tests/game/<mod>/save_checks.txt, if there is one (save-checks.txt), and, when this
#     version loaded the base version's save, the mod's names that save holds and this version
#     no longer mentions (dangling.txt). A failed check or a dangling name fails the run.
#
# Steps files, one step per line ('#' starts a comment):
#   shot NAME               screenshot to <report>/NN-NAME.png
#   click X Y               move the pointer to X,Y, wait 2 s, left-click
#   move X Y                move the pointer to X,Y
#   key KEYSYM...           xdotool key (X keysyms: Escape, Return, grave, space)
#   type TEXT               type TEXT
#   wait SECONDS            sleep
#   focus                   give the game's window the X input focus
#   info                    log windows, pointer, CPUs, memory and the game's RSS
#   until SECONDS REGEX     wait up to SECONDS for REGEX in logs/game.log; fails the run
#   untilsave DATE SECONDS  wait up to SECONDS for a save dated DATE (Y.M.D) or later; fails the run
#   clickuntil X Y SECONDS REGEX
#                           click X,Y every few seconds until game.log gains a line matching REGEX;
#                           fails the run after SECONDS
#   repeat SECONDS REGEX FILE
#                           follow steps FILE (next to this one) again and again until game.log
#                           gains a line matching REGEX; fails the run after SECONDS
#   clickchange X Y SECONDS RX RY RW RH
#                           click X,Y until the RW x RH pixels at RX,RY differ between two looks
#                           5 s apart (the date, once the game runs); fails the run after SECONDS
#   launch ARGS...          not a step: extra arguments for the game, read before it starts.
#                           %SAVE% stands for the name of the newest save in "save games"
#
# Env: CK2_GAME_DIR, CK2_USER_DIR  as for tools/smoke.sh
#      CAMPAIGN_OUT                reports (default campaign-reports/ in the repo)
#      CAMPAIGN_START, CAMPAIGN_END  dates (default 1067.1.1 and 1068.1.1: the 1066 start's first two
#                                  yearly autosaves)
#      CAMPAIGN_TIMEOUT            seconds each run may take to reach a date (default 1500)
#      CAMPAIGN_CACHE              a folder kept between runs (actions/cache): vanilla's save,
#                                  error lines and year, and base versions' saves; reused when there
#      CAMPAIGN_BASE               a commit with the previous version of the mods (the pull
#                                  request's base); unset, each mod loads vanilla's save
#      CAMPAIGN_PROBE_SAVE         --steps only: a save to put in "save games" first
#
# Measured on the fleet runner, PR #15's probe runs (2026-11-13): the game runs full screen at
# 1280x720; a click lands only when the pointer moved about 2 s before it; keys did not reach the
# game in runs 4 and 11; the menus take about 6 minutes under llvmpipe. Coordinates in the steps
# files were read off those runs' screenshots.
set -euo pipefail
repo=$(cd "$(dirname "$0")/.." && pwd)
game=${CK2_GAME_DIR:-/game}
ud=${CK2_USER_DIR:-$HOME/.paradoxinteractive/Crusader Kings II}
out=${CAMPAIGN_OUT:-$repo/campaign-reports}
start_date=${CAMPAIGN_START:-1067.1.1} end_date=${CAMPAIGN_END:-1068.1.1}
limit=${CAMPAIGN_TIMEOUT:-1500}
steps_dir=$repo/tools/campaign

probe=
if [ "${1:-}" = --steps ]; then probe=${2:?usage: tools/campaign.sh --steps FILE}; shift 2; fi
if [ "$#" -gt 0 ]; then
  mods=("$@")
elif [ -n "$probe" ]; then
  mods=()
else
  mods=()
  for d in "$repo"/mods/*/; do d=${d%/}; d=${d##*/}; [[ $d == _* ]] || mods+=("$d"); done
fi
for m in "${mods[@]}"; do
  [ -d "$repo/mods/$m" ] && [ -f "$repo/mods/$m.mod" ] || { echo "campaign: no mods/$m with mods/$m.mod" >&2; exit 2; }
done
[ -x "$game/ck2" ] || { echo "campaign: no executable ck2 in $game (set CK2_GAME_DIR)" >&2; exit 2; }
for t in Xvfb xdotool xwd xwdtopnm pnmtopng; do
  command -v "$t" >/dev/null || { echo "campaign: $t is not installed" >&2; exit 2; }
done
if pgrep -x ck2 >/dev/null; then echo "campaign: ck2 is already running" >&2; exit 2; fi
unshare -rn true 2>/dev/null || { echo "campaign: cannot give the game a network namespace (unshare -rn)" >&2; exit 2; }

export DISPLAY=:${CAMPAIGN_DISPLAY:-98} SDL_AUDIODRIVER=${SDL_AUDIODRIVER:-dummy} LIBGL_ALWAYS_SOFTWARE=1
Xvfb "$DISPLAY" -screen 0 1280x720x24 -nolisten tcp -noreset >/dev/null 2>&1 &
xvfb=$!
pid=
work=$(mktemp -d)
cleanup() { [ -z "$pid" ] || kill -9 "$pid" 2>/dev/null || true; kill "$xvfb" 2>/dev/null || true; rm -rf "$work"; }
trap cleanup EXIT
sleep 2
kill -0 "$xvfb" 2>/dev/null || { echo "campaign: Xvfb did not start on $DISPLAY" >&2; exit 2; }
rm -rf "$out"; mkdir -p "$out" "$ud/mod"
saves="$ud/save games"

# The game fills in the rest of settings.txt with its defaults (probe run 1: autosave="YEARLY",
# compress_autosaves=no). has_disabled_welcome_screen=yes skips the main menu's welcome dialog.
# The mapRenderingOptions keys are the ones the game wrote; turning the decorations off is meant to
# spare llvmpipe some work. [Unverified] how much that speeds the game up.
write_settings() {
  cat > "$ud/settings.txt" <<'SETTINGS'
gui=
{
	language=l_english
	has_set_language=yes
}
has_disabled_welcome_screen=yes
hints=no
mapRenderingOptions=
{
	draw_terrain=yes
	draw_water=no
	draw_borders=yes
	draw_trees=no
	draw_rivers=no
	draw_postfx=no
	draw_sky=no
	draw_bloom=no
	draw_tooltips=yes
	draw_hires_terrain=no
	draw_citysprawl=no
}
province_embellishment=no
SETTINGS
}

# Y.M.D -> a number that sorts like the date.
datenum() { local y m d; IFS=. read -r y m d <<< "$1"; echo $((10#$y * 10000 + 10#$m * 100 + 10#$d)); }
# newest_save: "MTIME PATH" of the newest save, MTIME in whole seconds.
newest_save() { find "$saves" -name '*.ck2' -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -n 1 | sed -E 's/^([0-9]+)[.0-9]* /\1 /'; }
# save_date FILE: the game date in a save, or nothing. Probe run 12 (2026-11-13) wrote two
# autosaves (21 and 24 MB, compress_autosaves=no) whose first 64 KB had no line starting with
# date=, so this reads the first MB, takes date= after any non-name character, and opens a zip.
save_date() {
  python3 -I - "$1" <<'PY' 2>/dev/null || true
import re, sys, zipfile
p = sys.argv[1]
if zipfile.is_zipfile(p):
    with zipfile.ZipFile(p) as z:
        name = max(z.infolist(), key=lambda i: i.file_size).filename
        data = z.open(name).read(1 << 20)
else:
    with open(p, 'rb') as f:
        data = f.read(1 << 20)
m = re.search(rb'(?:^|[^_A-Za-z0-9])date="?([0-9]+[.][0-9]+[.][0-9]+)', data)
if m:
    print(m.group(1).decode())
PY
}
# save_head FILE: the first bytes of a save, escaped, for the log.
save_head() { python3 -I -c 'import sys; print(repr(open(sys.argv[1], "rb").read(160)))' "$1" 2>/dev/null || true; }
# Lines compared without their leading [file:line]: tags, which move between game builds.
norm() { sed -E 's/\r$//; s/^(\[[^]]*\])+[[:space:]]*:?[[:space:]]*//; s/[[:space:]]+$//' "$@" | grep -v '^$' || true; }

dest='' n=0 result=''
log() { printf '%5ss %s\n' "$SECONDS" "$*" | tee -a "$dest/steps.log"; }
shot() {
  xwd -root -display "$DISPLAY" 2>/dev/null | xwdtopnm 2>/dev/null | pnmtopng > "$dest/$(printf '%02d' "$n")-$1.png" 2>/dev/null \
    || echo "campaign: screenshot $1 failed" >&2
}
fail() { result=$1; shot failed; }
# region X Y W H: a hash of those pixels on the screen, or nothing.
region() {
  xwd -root -display "$DISPLAY" 2>/dev/null | xwdtopnm 2>/dev/null | python3 -I -c '
import hashlib, sys
x, y, cw, ch = map(int, sys.argv[1:5])
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
rows = b"".join(px[((y + r) * w + x) * 3:((y + r) * w + x + cw) * 3] for r in range(ch))
print(hashlib.md5(rows).hexdigest()[:12])
' "$@" 2>/dev/null || true
}

# wait_save DATE SECONDS: wait for a save written after this call whose date is DATE or later, or
# whose date can't be read (then the first such save counts, with a warning); keep its path in
# $save. 1 when none comes. Saves written before the call (the mod runs' starting save) don't count.
save=
wait_save() {
  local want=$1 secs=$2 t0=$SECONDS since mt f got size
  since=$(date +%s)
  while :; do
    read -r mt f <<< "$(newest_save)" || true
    if [ -n "${f:-}" ] && [ "$mt" -gt "$since" ]; then
      size=-1   # the game writes a 20+ MB save over a few seconds: wait until it stops growing
      while [ "$size" != "$(stat -c %s "$f" 2>/dev/null)" ]; do size=$(stat -c %s "$f" 2>/dev/null); sleep 3; done
      got=$(save_date "$f")
      if [ -z "$got" ]; then
        log "  warning: no date found in $(basename "$f") ($size bytes), counting it as $want; it starts: $(save_head "$f")"
        save=$f; return 0
      fi
      if [ "$(datenum "$got")" -ge "$(datenum "$want")" ]; then
        log "  save dated $got after $((SECONDS - t0))s ($(basename "$f"), $size bytes)"; save=$f; return 0
      fi
      since=$mt
    fi
    if [ $((SECONDS - t0)) -ge "$secs" ] || ! kill -0 "$pid" 2>/dev/null; then
      log "  no save dated $want or later in $((SECONDS - t0))s"; return 1
    fi
    sleep 10
  done
}

# matches REGEX: how many game.log lines match REGEX.
matches() { local c; c=$(grep -acE "$1" "$ud/logs/game.log" 2>/dev/null) || true; echo "${c:-0}"; }
# launch_args FILE: the game arguments FILE's launch lines give, one per line, %SAVE% filled in.
launch_args() {
  local line cmd rest sv a words
  sv=$(newest_save) || true; sv=${sv#* }; sv=${sv##*/}
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%%#*}; read -r cmd rest <<< "$line" || true
    [ "${cmd:-}" = launch ] || continue
    read -ra words <<< "$rest"
    for a in "${words[@]}"; do printf '%s\n' "${a//%SAVE%/$sv}"; done
  done < "$1"
}

# run_steps FILE: follow a steps file; sets $result on a failure and returns 1.
run_steps() {
  local line cmd rest x y secs re t0 wid keys c0 file tries here rx ry rw rh h0 h1
  here=$(dirname "$1")
  while IFS= read -r line || [ -n "$line" ]; do
    line=${line%%#*}; read -r cmd rest <<< "$line" || true
    [ -n "${cmd:-}" ] && [ "$cmd" != launch ] || continue
    n=$((n + 1))
    kill -0 "$pid" 2>/dev/null || { log "step $n: the game is not running"; result=exited; return 1; }
    log "step $n: $cmd $rest"
    case $cmd in
      shot) shot "$rest" ;;
      click) read -r x y <<< "$rest"; xdotool mousemove "$x" "$y" sleep 2 click 1 ;;
      move) read -r x y <<< "$rest"; xdotool mousemove "$x" "$y" ;;
      key) read -ra keys <<< "$rest"; xdotool key --delay 150 "${keys[@]}" ;;
      type) xdotool type --delay 100 "$rest" ;;
      wait) sleep "$rest" ;;
      focus)
        wid=$(xdotool search --onlyvisible --name '^ck2$' 2>/dev/null | head -n 1 || true)
        if [ -n "$wid" ]; then xdotool windowfocus --sync "$wid" || true; log "  focus: $(xdotool getwindowfocus 2>&1)"; else log "  no ck2 window"; fi
        ;;
      info)
        { xdotool search --onlyvisible --name . getwindowname %@ getwindowgeometry %@; xdotool getmouselocation --shell
          echo "cpus: $(nproc)"; grep -E '^(MemTotal|MemAvailable)' /proc/meminfo; cat /sys/fs/cgroup/memory.max 2>/dev/null
          ps -o rss=,etime= -p "$pid" | awk '{print "ck2 rss MiB: " int($1/1024) ", running " $2}'; } 2>&1 | tee -a "$dest/steps.log" || true
        ;;
      until)
        read -r secs re <<< "$rest"
        t0=$SECONDS
        until grep -aqsE "$re" "$ud/logs/game.log"; do
          if [ $((SECONDS - t0)) -ge "$secs" ] || ! kill -0 "$pid" 2>/dev/null; then break; fi
          sleep 2
        done
        if grep -aqsE "$re" "$ud/logs/game.log"; then log "  found after $((SECONDS - t0))s"; else log "  not found in ${secs}s"; fail "timed out at step $n"; return 1; fi
        ;;
      untilsave) read -r x secs <<< "$rest"; wait_save "$x" "$secs" || { fail "no save by $x at step $n"; return 1; } ;;
      clickuntil)
        read -r x y secs re <<< "$rest"
        t0=$SECONDS c0=$(matches "$re") tries=0
        while [ "$(matches "$re")" -le "$c0" ]; do
          if [ $((SECONDS - t0)) -ge "$secs" ] || ! kill -0 "$pid" 2>/dev/null; then
            log "  no match in ${secs}s ($tries clicks)"; fail "timed out at step $n"; return 1
          fi
          xdotool mousemove "$x" "$y" sleep 2 click 1; tries=$((tries + 1))
          for _ in 1 2 3; do sleep 1; [ "$(matches "$re")" -le "$c0" ] || break; done
        done
        log "  matched after $((SECONDS - t0))s ($tries clicks)"
        ;;
      clickchange)
        # A click on a screen that is still loading is lost: PR #27's run 43531833583 clicked the
        # date 10 s after "Launching SINGLEPLAYER-game", before the map had finished drawing, and
        # the game stayed paused for 25 minutes. Both looks are taken with the pointer away.
        read -r x y secs rx ry rw rh <<< "$rest"
        t0=$SECONDS tries=0
        while :; do
          if [ $((SECONDS - t0)) -ge "$secs" ] || ! kill -0 "$pid" 2>/dev/null; then
            log "  nothing changed in ${secs}s ($tries clicks)"; fail "timed out at step $n"; return 1
          fi
          xdotool mousemove "$x" "$y" sleep 2 click 1 sleep 1 mousemove 640 600; tries=$((tries + 1))
          sleep 2; h0=$(region "$rx" "$ry" "$rw" "$rh"); sleep 5; h1=$(region "$rx" "$ry" "$rw" "$rh")
          [ -z "$h0" ] || [ "$h0" = "$h1" ] || break
        done
        log "  changed after $((SECONDS - t0))s ($tries clicks)"
        ;;
      repeat)
        read -r secs re <<< "$rest"; file=${re##* }; re=${re% *}
        t0=$SECONDS c0=$(matches "$re") tries=0
        while [ "$(matches "$re")" -le "$c0" ]; do
          if [ $((SECONDS - t0)) -ge "$secs" ] || ! kill -0 "$pid" 2>/dev/null; then
            log "  no match in ${secs}s ($tries rounds)"; fail "timed out at step $n"; return 1
          fi
          tries=$((tries + 1)); log "  round $tries of $file"
          run_steps "$here/$file" || return 1
          for _ in 1 2 3 4 5 6; do sleep 1; [ "$(matches "$re")" -le "$c0" ] || break; done
        done
        log "  matched after $((SECONDS - t0))s ($tries rounds)"
        ;;
      *) log "  unknown step"; fail "bad step $n"; return 1 ;;
    esac
  done < "$1"
}

# start NAME [game args...]: boot the game with a fresh report folder $dest.
start() {
  dest="$out/$1"; shift
  n=0 result=ok
  rm -rf "$dest" "$ud/logs"; mkdir -p "$dest"
  write_settings
  (cd "$game" && LD_LIBRARY_PATH="$game${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" exec unshare -rn ./ck2 -skiplauncher -debugscripts "$@") \
    > "$dest/stdout.log" 2>&1 &
  pid=$!
  log "started ck2 -skiplauncher -debugscripts $*"
}
# stop: end the game, keep its logs and the newest save's date.
stop() {
  n=$((n + 1)); shot end
  kill -0 "$pid" 2>/dev/null || { [ "$result" != ok ] || result=exited; }
  if [ -n "$pid" ]; then
    kill "$pid" 2>/dev/null || true
    for _ in 1 2 3 4 5; do kill -0 "$pid" 2>/dev/null || break; sleep 1; done
    kill -9 "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; pid=
  fi
  cp "$ud"/logs/*.log "$dest/" 2>/dev/null || true
  log "result: $result"
}

if [ -n "$probe" ]; then
  rm -rf "$saves"
  if [ -n "${CAMPAIGN_PROBE_SAVE:-}" ]; then mkdir -p "$saves"; cp -p "$CAMPAIGN_PROBE_SAVE" "$saves/"; fi
  mapfile -t args < <(launch_args "$probe")
  start probe "${args[@]}"
  run_steps "$probe" || true
  stop
  [ "$result" = ok ]
  exit
fi

# 1. vanilla, from a new game, or from CAMPAIGN_CACHE when an earlier run left it there. The game
# never changes (3.3.5.1 is the last version), so vanilla's run depends only on this script and its
# steps files, which the workflow's cache key hashes.
cache=${CAMPAIGN_CACHE:-}
if [ -n "$cache" ] && [ -f "$cache/vanilla/start.ck2" ] && [ -f "$cache/vanilla/error.norm" ]; then
  dest="$out/_vanilla"; mkdir -p "$dest"
  cp -p "$cache/vanilla/start.ck2" "$work/"
  cp "$cache/vanilla/error.norm" "$dest/"
  cp "$cache/vanilla/steps.log" "$dest/cached-steps.log" 2>/dev/null || true
  cp "$cache/vanilla/year-seconds" "$dest/" 2>/dev/null || true
  log "vanilla: restored from the cache ($(cat "$cache/vanilla/made-by" 2>/dev/null || echo unknown run)), not run"
else
  rm -rf "$saves"
  mapfile -t args < <(launch_args "$steps_dir/new_game.txt")
  start _vanilla "${args[@]}"
  if run_steps "$steps_dir/new_game.txt"; then
    if wait_save "$start_date" "$limit"; then
      cp -p "$save" "$work/start.ck2"
      log "  kept $(basename "$save") as the start for the mod runs"
      t0=$SECONDS
      if wait_save "$end_date" "$limit"; then echo $((SECONDS - t0)) > "$dest/year-seconds"; else fail "vanilla did not reach $end_date"; fi
    else
      fail "vanilla did not reach $start_date"
    fi
  fi
  stop
  vanilla=$result
  norm "$out/_vanilla/error.log" 2>/dev/null | sort -u > "$out/_vanilla/error.norm"
  if [ "$vanilla" != ok ] || ! [ -f "$work/start.ck2" ]; then
    echo "campaign: vanilla run failed ($vanilla); see $out/_vanilla" >&2
    exit 1
  fi
  if [ -n "$cache" ]; then
    rm -rf "$cache/vanilla"; mkdir -p "$cache/vanilla"
    cp -p "$work/start.ck2" "$out/_vanilla/error.norm" "$out/_vanilla/steps.log" "$cache/vanilla/"
    cp "$out/_vanilla/year-seconds" "$cache/vanilla/" 2>/dev/null || true
    echo "run ${GITHUB_RUN_ID:-local} on $(date -u +%Y-%m-%d)" > "$cache/vanilla/made-by"
  fi
fi

# 2. each mod, from vanilla's save
failed=()
next_year() { local y m d; IFS=. read -r y m d <<< "$1"; echo "$((10#$y + 1)).$m.$d"; }
for m in "${mods[@]}"; do
  prefix=$(tr -d '[:space:]' < "$repo/mods/$m/PREFIX" 2>/dev/null || true)
  rm -rf "$saves"; mkdir -p "$saves"; cp -p "$work"/*.ck2 "$saves/"
  from="vanilla's $start_date save" to=$end_date loaded=
  # 2a. a mod that CAMPAIGN_BASE has and this version changes: play the year with the base version
  # first, so this version loads a save that holds the old version's state.
  if [ -n "${CAMPAIGN_BASE:-}" ] && git -C "$repo" cat-file -e "$CAMPAIGN_BASE:mods/$m.mod" 2>/dev/null &&
     ! git -C "$repo" diff --quiet "$CAMPAIGN_BASE" -- "mods/$m" "mods/$m.mod"; then
    rm -rf "$work/upgrade"; mkdir -p "$work/upgrade"
    # The base version's save depends only on that version's files (and this script, which the
    # cache key hashes), so it is kept under their tree's hash.
    based=""; [ -z "$cache" ] || based="$cache/base/$m-$(git -C "$repo" rev-parse "$CAMPAIGN_BASE:mods/$m").ck2"
    if [ -n "$based" ] && [ -f "$based" ]; then
      cp -p "$based" "$work/upgrade/"
      dest="$out/$m.base"; mkdir -p "$dest"; log "the ${CAMPAIGN_BASE:0:12} version's save: restored from the cache, not run"
    else
      rm -rf "$work/base" "${ud:?}/mod/$m"; mkdir -p "$work/base" "$ud/mod"
      git -C "$repo" archive "$CAMPAIGN_BASE" "mods/$m" "mods/$m.mod" | tar -x -C "$work/base"
      cp -r "$work/base/mods/$m" "$ud/mod/$m"; cp "$work/base/mods/$m.mod" "$ud/mod/"
      mapfile -t args < <(launch_args "$steps_dir/continue.txt")
      start "$m.base" "-mod=mod/$m.mod" "${args[@]}"
      log "the version in ${CAMPAIGN_BASE:0:12}, to make a save with its state"
      if run_steps "$steps_dir/continue.txt" && wait_save "$end_date" "$limit"; then
        cp -p "$save" "$work/upgrade/"
        if [ -n "$based" ]; then mkdir -p "$cache/base"; cp -p "$save" "$based"; fi
      else
        [ "$result" != ok ] || fail "did not reach $end_date"
      fi
      stop
      rm -rf "${ud:?}/mod/$m" "$ud/mod/$m.mod"
    fi
    if compgen -G "$work/upgrade/*.ck2" >/dev/null; then
      rm -rf "$saves"; mkdir -p "$saves"; cp -p "$work"/upgrade/*.ck2 "$saves/"
      from="the ${CAMPAIGN_BASE:0:12} version's $end_date save" to=$(next_year "$end_date")
      loaded=$(compgen -G "$work/upgrade/*.ck2" | head -n 1)
    else
      log "  the base version made no save; this version loads vanilla's save instead"
      from="vanilla's $start_date save (the base version's run failed: see $m.base)"
    fi
  fi
  # 2b. this version. A copy, not install.sh's link: tools/harness.py marks each event and adds
  # tests/game/$m.
  python3 "$repo/tools/harness.py" install "$m" "$ud/mod/$m"
  cp "$repo/mods/$m.mod" "$ud/mod/"
  mapfile -t args < <(launch_args "$steps_dir/continue.txt")
  start "$m" "-mod=mod/$m.mod" "${args[@]}"
  if run_steps "$steps_dir/continue.txt"; then
    if wait_save "$to" "$limit"; then cp -p "$save" "$work/last.ck2"; else fail "did not reach $to"; fi
  fi
  stop
  rm -rf "${ud:?}/mod/$m" "$ud/mod/$m.mod"
  dest="$out/$m"
  hs=0; python3 "$repo/tools/harness.py" report "$m" "$dest/game.log" > "$dest/harness.txt" || hs=$?
  # The save's state: checks from tests/game/$m/save_checks.txt on the last save, and names the
  # base version's save holds that this version dropped (#20: the game logs nothing for those).
  ss=0
  {
    echo "Save checks: $m"
    if [ -f "$repo/tests/game/$m/save_checks.txt" ]; then
      if [ -f "$work/last.ck2" ]; then
        python3 "$repo/tools/ck2save.py" "$work/last.ck2" check "$repo/tests/game/$m/save_checks.txt" || ss=1
      else
        echo "CK2SAVE fail no save from this run to check"; ss=1
      fi
    else
      echo "no tests/game/$m/save_checks.txt"
    fi
    if [ -n "$loaded" ] && [ -n "$prefix" ]; then
      dirs=("$repo/mods/$m"); [ ! -d "$repo/tests/game/$m" ] || dirs+=("$repo/tests/game/$m")
      if python3 "$repo/tools/ck2save.py" "$loaded" dangling "$prefix" "${dirs[@]}" > "$dest/dangling.txt"; then
        echo "dangling names in the base version's save: none"
      else
        echo "CK2SAVE fail dangling names: the base version's save holds these, and this version no longer mentions them"
        echo "(remove nothing old saves hold, or label the pull request save-breaking):"
        cat "$dest/dangling.txt"; ss=1
      fi
    fi
  } > "$dest/save-checks.txt"
  rm -f "$work/last.ck2"
  # 3. new lines, split by whether they name the mod
  norm "$dest/error.log" 2>/dev/null | grep -vxF -f "$out/_vanilla/error.norm" | sort | uniq -c | sort -rn > "$dest/new-errors.txt" || true
  {
    printf '%s\n' "$m"
    [ -z "$prefix" ] || printf '%s_\n%s.\n' "$prefix" "$prefix"
    (cd "$repo/mods/$m" && find . -type f ! -name PREFIX ! -name README.md -printf '%f\n')
    [ ! -d "$repo/tests/game/$m" ] || find "$repo/tests/game/$m" -type f -printf '%f\n'
  } | grep -v '^$' | sort -u > "$dest/names.txt"
  grep -iF -f "$dest/names.txt" "$dest/new-errors.txt" > "$dest/mod-errors.txt" || true
  grep -viF -f "$dest/names.txt" "$dest/new-errors.txt" > "$dest/other-errors.txt" || true
  nm=$(grep -c . "$dest/mod-errors.txt" || true) no=$(grep -c . "$dest/other-errors.txt" || true)
  seen=false
  if grep -aqsF "mod/$m" "$dest/system.log"; then seen=true; fi
  {
    echo "CK2 campaign test: $m"
    echo "result: $result ($from loaded with this version, run to $to)"
    echo "mod named in logs: $seen"
    echo "new error.log lines that name the mod: $nm"
    cat "$dest/mod-errors.txt"
    echo "other new error.log lines (warnings; the game's own runtime errors vary between runs): $no"
    head -n 50 "$dest/other-errors.txt"
    echo
    cat "$dest/harness.txt"
    echo
    cat "$dest/save-checks.txt"
  } > "$dest/report.txt"
  cat "$dest/report.txt"
  if [ "$result" != ok ] || [ "$nm" -gt 0 ] || [ "$seen" != true ] || [ "$hs" -ne 0 ] || [ "$ss" -ne 0 ]; then failed+=("$m"); fi
done
[ "${#failed[@]}" -eq 0 ] || { echo "failed: ${failed[*]}"; exit 1; }
echo "all mods clean: ${mods[*]}"
