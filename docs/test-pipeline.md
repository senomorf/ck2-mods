# Test pipeline

How a mod change gets checked, from cheapest to closest to the real game, and what each self-hosted
runner must provide. Host setup (installing runners, game files, isolation) is done from the owner's
homelab repo; this file is the contract those hosts must meet. Each section says what is verified.

Host work is tracked in the homelab repo: senomorf/homelab#2320 (public-repo decision),
senomorf/homelab#2321 (Windows runner on Polaris: closed, none planned), senomorf/homelab#2322
(Linux headless game: the runner exists). This repo's half of the Linux runner: #10.

## Layers

What comes next, from runtime checks to save loading, is planned in #13.


| Layer | Where | What it catches | Status |
| --- | --- | --- | --- |
| Lint (`tools/lint.py`) | CI on GitHub-hosted runners, cloud sessions | encoding, braces, duplicate ids, localisation format | working |
| Cross-references (`tools/xref.py`, part of lint) | same | fired events that don't exist, flags set but never read, unsaved event targets, decisions without text | working; in CI only names with the mod's prefix (no `vanilla/` there) |
| CWTools (`lint.py --cwtools`) | cloud sessions (needs `cwtools` and `vanilla/`) | unknown effects, triggers, scopes, traits | working; warnings only, noisy on vanilla |
| Static with the game's files (`linux static` job) | the fleet runner, against its game copy at `/game` | the same lint and cross-references, with all of vanilla's names; CWTools in CI | working: lint, cross-references and CWTools `--strict` (red run on #14: `CW262` for an unknown effect) |
| Linux smoke (`tools/smoke.sh`) | the homelab fleet's runner, `linux smoke` job | anything the game itself logs at boot: parse errors, unknown keys, broken references | working: green and red runs on same-repo PRs (#10); see [Linux runner](#linux-runner) |
| Linux campaign (`tools/campaign.sh`) | the fleet runner, `linux campaign` job (`campaign.yml`) | errors the game logs while it plays a year with the mod, and loading a save made without it. Not runtime script faults: dividing by a zero variable and an unsaved event target logged nothing ([red run](https://github.com/senomorf/ck2-mods/actions/runs/43486984204/job/132097929990) on #17); in-game tests catch what those break | working: [green run](https://github.com/senomorf/ck2-mods/actions/runs/43468936925/job/132035403675) on #15 with `allied_fleets` (red run pending); see [Campaign test](#campaign-test) |
| Windows smoke (`tools/smoke.ps1`) | the owner's PC (Polaris), by hand | same, on the Windows build | script written; launch arguments unverified; no runner planned |
| In-game tests (`tools/harness.py`, `tests/game/<mod>/`) | the `linux campaign` job, in each mod's run | events that never fire, effects that don't do what they should: test events check the mod's state and log pass or fail | working: first [run](https://github.com/senomorf/ck2-mods/actions/runs/43475355959) (#18) fired all 3 `allied_fleets` events (afl.1 20 times, afl.2 15, afl.3 5) and passed 35 checks; the [red run](https://github.com/senomorf/ck2-mods/actions/runs/43486984204/job/132097929990) on #17 failed on a deliberately broken check, 20 times |

Why runners: the game can't run in a Claude cloud session. The agent proxy carries neither the
WebSocket nor the raw TCP connections Steam login needs (`/root/.ccr/README.md`, "Not supported
through the proxy"), and a several-GB game install doesn't belong in a session. The fleet runner
keeps a copy of the game instead.

## Workflow

`.github/workflows/smoke.yml` has two jobs:

| Job | Runs on | Switched on by |
| --- | --- | --- |
| `linux static` | `[self-hosted, linux, ck2]`, the fleet runner | always. Links `vanilla/` to `/game`, runs `tools/lint.py`, then `tools/cwtools_check.py --strict` when `cwtools` is installed; a missing tool skips its step with a warning |
| `linux smoke` | `[self-hosted, linux, ck2]`, the fleet runner | always (no variable: sessions can't set repository variables) |
| `windows smoke` | `[self-hosted, windows, ck2]` | repository variable `CK2_SMOKE_WINDOWS=true`; unset, the job is skipped rather than left queued. No Windows runner is planned |

Jobs run on pushes to `main`,
pull requests **from branches of this repository only** (`head.repo.full_name == github.repository`), except Renovate's (author `renovate[bot]` or branch `renovate/*`),
and by hand (`workflow_dispatch`). The job-level `if` is evaluated before a runner is assigned, so a fork's
pull request never reaches a self-hosted runner. See [Security](#security).

So a Renovate update to an action in `smoke.yml` first runs on the fleet runner after it merges, on `main`.
Watch that run, and revert the update if it fails there.

Each job smokes every mod the push or pull request changed, and every mod on a manual run. The
Linux job also smokes every mod when `tools/smoke.sh`, `tools/install.sh` or the workflow changed,
or when git can't tell what changed, and skips the boot when no mod changed. Each job uploads its
reports as an artifact (`smoke-linux`, `smoke-windows`) and fails on any new `error.log` line.
The Linux job also reads the multiplayer checksum: the main menu's version label, e.g.
`3.3.5.1 (SOHY)`, is the only place the game shows it, so each boot saves the label as
`version.png` and the report says whether a mod's label differs from vanilla's. One that differs
changes the checksum: label the pull request `mp-checksum`, and every multiplayer player needs the
same release. It warns rather than fails, since most gameplay mods change it.

## Windows runner contract

| Need | Detail |
| --- | --- |
| Labels | `self-hosted`, `windows`, `ck2` |
| Registration | repository runner for `senomorf/ck2-mods` only, ephemeral preferred |
| Session | an **interactive desktop session**. CK2 is a DirectX game and needs a desktop, so the runner can't be a Windows service in session 0. Start `run.cmd` from a logon task in the session that will run the game |
| Game | CK2 installed by Steam, path in env `CK2_GAME_DIR` (default `C:\Program Files (x86)\Steam\steamapps\common\Crusader Kings II`) |
| User dir | env `CK2_USER_DIR`. `smoke.ps1` writes there: it links the mod into `mod\`, deletes and copies `logs\`. Use a user dir that isn't the owner's play profile if possible |
| Steam | [Unverified] whether CK2 starts without the Steam client running. The first run must find out |
| Exclusivity | one CK2 at a time: `smoke.ps1` refuses when `CK2game.exe` already runs. The runner should be online only while nobody uses the PC, like the homelab transcode encoder's idle gate |
| Baseline | `smoke.ps1 -Baseline` after every game update and on first setup; it is stored in `%LOCALAPPDATA%\ck2-mods\smoke\_baseline\` |
| Tools | Windows PowerShell 5.1, git. No Python needed |

To verify on the first run, then record in `docs/ck2-notes.md`:

1. Does `CK2game.exe -skiplauncher` boot straight to the main menu?
2. Does `-mod=mod/<folder>.mod` load the mod? Check the in-game mod list, or a deliberate error in the mod showing in `error.log`.
3. Does `error.log` stop growing once the main menu is up? That is the "booted" signal `smoke.ps1` waits for.
4. How long does a boot take?

## Linux runner

The homelab fleet runs it (senomorf/homelab#2322); what it provides, per #10:

| Need | Detail |
| --- | --- |
| Runner | `dunkirk-ck2mods-1`, a repository runner for `senomorf/ck2-mods`, ephemeral (a fresh container per job) |
| Labels | `ck2`, `dunkirk`, and the defaults `self-hosted`, `Linux`, `X64` |
| Game | CK2 3.3.5.1, native Linux build, read-only at `/game` (`CK2_GAME_DIR` defaults to it) |
| User dir | env `CK2_USER_DIR`, set by the runner |
| Display | Xvfb plus Mesa's software OpenGL (llvmpipe) |
| Network | public only |
| Tools | `python3` 3.12.3, Xvfb, `xwd` and netpbm, `xdotool`, the CWTools CLI 0.6.0-alpha on the .NET 10 runtime with `DOTNET_ROLL_FORWARD=Major` (no SDK; senomorf/homelab#2411). A `cwtools_check.py` run peaked at 2.28 GiB RSS in a cloud session (2026-11-13); the job is capped at 3 GiB |

What `tools/smoke.sh` relies on, measured on that runner (#10, 2026-11-13):

- **Booted** means `game.log` gains `After first history execution`. A boot took 20 to 30 s under
  llvmpipe, 70 s once with the host busy. The script keeps the game running 15 s more, then kills it.
- **Language dialog**: an empty user folder stops at "Choose language" and waits for a click.
  `settings.txt` with `gui = { language=l_english has_set_language=yes }` skips it;
  `language="l_english"` alone does not. The script writes that file when it lacks `has_set_language`.
- **No Steam client, no network**: the game logs `SteamAPI_Init() failed` and carries on, but only
  without a network. With one it prints "Please start Crusader Kings II through steam for your
  first time start-up" and exits 1 after about 16 s. So the game runs in its own network namespace
  (`unshare -rn`, only a downed loopback), while the job keeps its network for GitHub.
- **Xvfb runs with `-noreset`**. Without it Xvfb resets when its last client disconnects, and a
  connection made meanwhile fails. One boot right after the baseline's died at once with
  "Failed to initialize SDL! SDL_Error: No available video device"
  ([run](https://github.com/senomorf/ck2-mods/actions/runs/43421049097/job/131870832530)). A
  close-then-reopen test in a cloud session (Xvfb 21.1) failed 5 of 600 times without `-noreset`
  and 0 of 600 with it.
- **Baseline**: the runner keeps nothing between jobs, so each run boots vanilla first and compares
  each mod's `error.log` with it, ignoring the leading `[file:line]` tags.
- **Mod loaded**: `system.log` names `mod/<folder>` when the game loads the mod, and a vanilla boot
  doesn't. A mod whose name is missing fails even with no new errors.
- The script refuses (exit 2) without an executable `ck2`, Xvfb, or `unshare -rn`, or when `ck2`
  already runs. It saves `report.txt`, `new-errors.txt` and the logs per mod in `smoke-reports/`,
  plus `screen.png` (with `xwd` and netpbm) when a boot fails.

Tested in the runner image before the job existed (#10): a clean `allied_fleets` gave 0 new error
lines, a copy with an unknown effect 4. In the job, 2026-11-13: [green](https://github.com/senomorf/ck2-mods/actions/runs/43420436244/job/131868779709) on #7 (booted after
24 s, mod named, 0 new lines) and [red](https://github.com/senomorf/ck2-mods/actions/runs/43420596435/job/131869314332) on throwaway #12, whose one new line was
`Unknown effect-type: "afl_no_such_effect" at  file: events/afl_events.txt line: 16`.

## Campaign test

`tools/campaign.sh` plays the game for a year (#13, step 2). `.github/workflows/campaign.yml` runs it
on the fleet runner for pushes to `main` and same-repo pull requests that change a mod, the script,
its steps files or `tools/install.sh`, and by hand. It picks mods the way the smoke job does.

1. Vanilla: a new 1066 game (`tools/campaign/new_game.txt`: launch options `-startgame
   -start_date=1066.9.15` open the character selection, skipping the menus), the console command
   `observe` so no character waits for input, the fastest speed, run to the first yearly autosave
   (1067.1.1). That save is kept, and the game runs on to the next one (1068.1.1). With slow menus
   the 1067.1.1 autosave can come while the steps still run (it counts) or be passed: then the
   first save after it is kept, a later run logs `vanilla's start save is dated ...`, and every run
   counts its year from that save's date. (Before this, `main`'s run 43530660714 kept 1068.1.1 and
   its report still said 1067.1.1.)
2. Each mod: the kept save is put back as the only save, and the game boots with the mod straight
   into it (`tools/campaign/continue.txt`: `-startgame -start_save=<save>`); it runs to 1068.1.1. So each
   mod plays the same year vanilla did, from a save made without it, which also checks that an
   existing save loads with the mod.
   When the push or pull request changes a mod that its base commit already has, the base's
   version of the mod plays that year first, and this version loads the save it made and plays the
   next year (to 1069.1.1). So a save holding the old version's flags, modifiers and characters
   must load with the new one (CLAUDE.md: keep existing saves loading). The base version's run is
   in `<mod>.base/` in the artifact; if it fails, this version loads vanilla's save instead. It adds
   about 12 minutes per such mod. Manual runs have no base, so they skip it.
3. New `error.log` lines against the vanilla run are split by whether they name the mod (its
   folder, prefix or a file name). Those fail the job; the rest are listed as warnings, because
   the game's own runtime errors differ from run to run. A mod whose name `system.log` lacks fails.
   `error.log` shows what the game finds wrong while loading files and some runtime problems, but
   not script mistakes that run without complaint: on #17 an event that divided by a zero
   variable and scoped to a never-saved event target ran 348 times and logged nothing, in
   `error.log` or any other log. Behaviour needs in-game tests (below).

In each mod's run the mod is a copy made by `tools/harness.py install`, not install.sh's link. The
copy gets trace lines (#38, step 1): `CK2TEST fired <id> root=<character id>` at the start of every
event's `immediate` block (one is added where an event has none), `CK2TEST chose <id> <option>` at
the start of every option, `CK2TEST took <decision>` in every decision's `effect`, and `CK2TEST ran
<effect>` in every scripted effect. `root=` and `from=` come from `[Root.GetID]` and
`[From.GetID]`, and are written only where that scope is a character. Each `game.log` line carries
the game date (`EVENT [1067.1.2]:CK2TEST fired afl.1 root=<id>`). The copy also gets the files
under `tests/game/<mod>/`, laid out like the mod (`events/`, `common/on_actions/`). Those are test
events: they set up a situation, fire the mod's events, and log `CK2TEST pass <check>` or `CK2TEST
fail <check>`, then `CK2TEST done`. A check's name is the text before the first `: `, so a failure
can add values after it (`CK2TEST fail gold moves: [Root.afltest_paid.GetValue]`). A check that a
test file names but that never reports fails the run (#38, step 2). `tests/game/<mod>/log_checks.txt`
adds checks on the counts: `count fired afl.2 == count chose afl.1 EVTOPTA_afl_1`, `count chose
afl.1 EVTOPTB_afl_1 >= 1`, or `count line <text> >= 1` for the mod's own log lines (format in
`tools/harness.py`). The `log` effect writes to `game.log` under `-debugscripts`
(`vanilla/ChangeLog.txt`). `tools/harness.py report` turns those lines into `harness.txt`: how
often each event fired and each option was chosen, for how many characters, from what date; each
decision and scripted effect; and each check. A failed check fails the run. For a mod with tests,
so does a missing `done`, an event that never fired, an option never chosen, a scripted effect
that never ran, a check that never reported or a failed log check. Decisions are only counted, since no script can take a decision. A mod without
tests only gets its traces counted. `on_startup` starts the tests: it fires for every
character when a save loads (`.cwtools/on_actions.cwt`), so test events guard with a global flag.

`report.txt` also gives the mod's speed: the seconds its year took against vanilla's year, as a
ratio, with a warning annotation above 1.5 (`CAMPAIGN_SLOW_RATIO`). It never fails the run, since
both years share the host with whatever else runs there: the live test box and the runner are on
the same machine, and on #27's run, with box runs going at the same time, vanilla's year took 545 s
against 134 s on #24's. Even with the box stopped, vanilla's year swung from 214 s (#31's run) to
73 s (#34's) while the mod's stayed near 200 s, so the first ratio is 0.86 one run and 2.79 the
next. Vanilla's year runs in the game it started, and each mod's from a freshly loaded save. So
above the threshold, vanilla plays the year again in the same job, loading the same save and timed
the same way, and only that second ratio warns. `report.txt` gives both. Next to each wall-clock
figure it gives the game's CPU seconds for the year (user and system, all its threads, from
`/proc`), and `steps.log` has a line per year with the host's load average, available memory, the
job's cgroup CPU limit and how long that limit held the job back. These are not gated on yet: #40
collects them to find out whether CPU seconds stay steady between jobs when wall seconds do not.

After the year, `tools/ck2save.py` reads the run's last autosave (plain Clausewitz text, since the
script sets `compress_autosaves=no`) into `save-checks.txt`:

- `tests/game/<mod>/save_checks.txt`, if there is one: checks on the state the year left, one per
  line, `present NAME` / `absent NAME` (a flag, modifier, earmark or event id anywhere in the save)
  or `count PATH OP N` (`count character/*/flags/afl_test_requester >= 1`). A failed check fails the
  run. The harness does not copy this file into the mod.
- When this version loaded the base version's save: the names with the mod's prefix that save holds
  and that this version's files (and tests) no longer mention. Any fails the run, since the game
  logs nothing for them (#20: a deleted modifier that old saves held loaded and ran without a line).
  Keep what old saves hold, or label the pull request `save-breaking`.

`python3 tools/ck2save.py SAVE info|get PATH|names PREFIX|check FILE|dangling PREFIX DIR...` does
the same by hand, on a save from the artifact or the owner's game.

### Trying effects by hand

The console's `run FILE` runs a file of effects (`docs/ck2-notes.md`). With the live test box a
session can load a save, fire a mod's event or run its effects, and read the result in about a
minute, instead of a campaign run:

```
tools/box-run.sh env CAMPAIGN_PROBE_SAVE=.box/start.ck2 CAMPAIGN_PROBE_EFFECTS=.box/fx.txt \
  CAMPAIGN_PROBE_MOD=allied_fleets tools/campaign.sh --steps tools/campaign/run_effects.txt
```

`tools/box-run.sh` copies the working tree's `tools/`, `mods/` and `tests/`, plus the gitignored
`.box/` folder for saves and scratch files, to the box, runs the command there and brings
`campaign-reports/` back. A save to start from: any yearly autosave in a campaign run's artifact.
`ssh ck2box box-stop` when done, since the box shares the CI runner's memory.

The effects run in no character's scope (observe mode), so start them with a scope such as
`random_independent_ruler = { ... }`, and add `log = "..."` lines to see what happened in
`campaign-reports/probe/game.log`. With a mod, the harness copy logs `CK2TEST fired <id>` for each of
its events, and its in-game tests start too (from the save's first day).

The runner keeps nothing between jobs, so the workflow keeps `.campaign-cache/` in `actions/cache`
(`CAMPAIGN_CACHE`), keyed on the hash of `tools/campaign.sh` and `tools/campaign/**`: vanilla's
1067.1.1 save, its normalised `error.log` lines and its year's duration, and each base version's
save under the hash of that version's files. The game never changes (3.3.5.1 is final), so a run
with a warm cache skips vanilla, and skips a base version it has seen. The cache is saved even when
a mod fails, and a change to the script or its steps files starts a new one.

The steps files are xdotool clicks, keys and waits, with a screenshot at each `shot`; a `launch`
line in a steps file adds launch options. The game writes few `game.log` lines, but enough to wait
on instead of timers: `clickuntil` clicks until a line appears (the lobby's random-character button
until "set as primary local", Game Rules' Start Game until "Launching SINGLEPLAYER-game"), and
`repeat` follows a short steps file until one does (closing the start splash and typing `observe`
until "unset as primary local"). Unpausing has no log line, so `clickchange` clicks the date until
its pixels change between two screenshots 5 s apart, and again over the next 5 s: a click while the
loaded map was still drawing was lost on PR #27's
[run 43531833583](https://github.com/senomorf/ck2-mods/actions/runs/43531833583), and the game sat
paused until the timeout. One change was not enough: on a box run (2026-11-14) the region changed
once 11 s after launch, likely the top bar's first draw, while the game stayed paused at 1067.1.1
for 25 minutes. A running date keeps changing. Two changes were not enough either: on a later box
run they passed after one click while the date's pixels were the same in every screenshot of the
run, and the game again sat paused. So the region also takes in the speed sign, which is red while
paused and has no red while running, and the last two looks must have no red pixel. A failed
screenshot is not a change. Each look's hash and red count go to `steps.log`. The fixed waits left are margins of a few seconds. On the live test
box (2026-11-13) a new game was running at full speed 123 s after launch, against 381 s on #15's
run through the menus. The artifact
`campaign-linux` holds them with `steps.log`, the logs and `report.txt` per run. What the steps
rely on, measured on PR #15's probe runs, is in `docs/ck2-notes.md`: clicks need the pointer moved
about 2 s before, and keys need the window focused. On the [green run](https://github.com/senomorf/ck2-mods/actions/runs/43468936925/job/132035403675) (#15, 2026-11-13) the menus
took 7.5 minutes, vanilla reached 1067.1.1 at 10 minutes and 1068.1.1 at 18, and `allied_fleets`
took 12.3 minutes from boot to 1068.1.1: 30 minutes for one mod, plus about 12 for each further mod.
The game used up to 2 GiB of the job's 3 GiB on the runner's 4 CPUs. `tools/campaign.sh --steps FILE` follows one steps file from a vanilla boot and
keeps everything, for working out new steps.

## Security

The repository is **public**. GitHub's documentation has recommended against self-hosted runners on
public repositories, because a fork's pull request can run its code on the runner (older wording,
quoted in [this thread](https://github.community/t/self-hosted-runner-security-with-public-repositories/17860);
current page: [adding runners](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners)). Defences, in order:

1. The workflow's job-level `if` admits only pushes, same-repository pull requests and manual runs.
2. Repository setting: Actions > General > "Require approval for all external contributors".
3. The runner account is separate from the owner's, with no access to the owner's files or credentials, and egress limited to what the job needs (GitHub).
4. Or make the repository private, which removes the fork risk. It's the owner's decision.

The workflow file can be edited by anyone who can push a branch here. That's only the owner and
agent sessions acting for them.

## Game files in cloud sessions

Script files only (no binaries), CK2 3.3.5.1, are cached in the Claude project's shared files and
unpacked into `vanilla/` by the session hook. They are enough for lint, cross-references and CWTools, not for running the game.
See the `game-files` skill.
