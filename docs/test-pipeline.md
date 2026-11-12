# Test pipeline

How a mod change gets checked, from cheapest to closest to the real game, and what each self-hosted
runner must provide. Host setup (installing runners, game files, isolation) is done from the owner's
homelab repo; this file is the contract those hosts must meet. Nothing here is verified on a runner
yet: each section says what is.

Host work is tracked in the homelab repo: senomorf/homelab#2320 (public-repo decision),
senomorf/homelab#2321 (Windows runner on Polaris), senomorf/homelab#2322 (Linux headless game).

## Layers

| Layer | Where | What it catches | Status |
| --- | --- | --- | --- |
| Lint (`tools/lint.py`) | CI on GitHub-hosted runners, cloud sessions | encoding, braces, duplicate ids, localisation format | working |
| Cross-references (`tools/xref.py`, part of lint) | same | fired events that don't exist, flags set but never read, unsaved event targets, decisions without text | working; in CI only names with the mod's prefix (no `vanilla/` there) |
| CWTools (`lint.py --cwtools`) | cloud sessions (needs `cwtools` and `vanilla/`) | unknown effects, triggers, scopes, traits | working; warnings only, noisy on vanilla |
| Windows smoke (`tools/smoke.ps1`) | the owner's PC (Polaris), by hand or a self-hosted runner | anything the game itself logs at boot: parse errors, unknown keys, broken references | script written; launch arguments unverified |
| Linux smoke (to be written: `tools/smoke.sh`) | a Linux self-hosted runner with the CK2 Linux build | same as Windows, without the owner's PC | not started; needs a host with the game |
| Scripted in-game checks | either runner, after the smoke | events firing, decisions available, effects applied | idea only: the console `run <file>` command could fire each event; unverified |

Why runners: the game can't run in a Claude cloud session. The agent proxy carries neither the
WebSocket nor the raw TCP connections Steam login needs (`/root/.ccr/README.md`, "Not supported
through the proxy"), and a several-GB game install doesn't belong in a session. A host with direct
internet can log in to Steam once and keep the game.

## Workflow

`.github/workflows/smoke.yml` runs the smoke on each runner that is switched on:

| Repository variable | Effect |
| --- | --- |
| `CK2_SMOKE_WINDOWS=true` | the `windows smoke` job runs on `[self-hosted, windows, ck2]` |
| `CK2_SMOKE_LINUX=true` | the `linux smoke` job runs on `[self-hosted, linux, ck2]` |

With a variable unset, its job is skipped rather than left queued. Jobs run on pushes to `main`,
pull requests **from branches of this repository only** (`head.repo.full_name == github.repository`),
and by hand (`workflow_dispatch`). The job-level `if` is evaluated before a runner is assigned, so a fork's
pull request never reaches a self-hosted runner. See [Security](#security).

Each job smokes every mod the push or pull request changed (all mods on `main` and by hand). It
uploads the report as an artifact and fails on any new `error.log` line.

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

## Linux runner contract

| Need | Detail |
| --- | --- |
| Labels | `self-hosted`, `linux`, `ck2` |
| Registration | repository runner for `senomorf/ck2-mods` only, ephemeral preferred |
| CPU | x86_64. [Unverified] whether 3.3.3's Linux binary is 32- or 64-bit: forum reports conflict ([thread](https://admin-forum.paradoxplaza.com/forum/threads/what-is-the-graphics-system-for-ck2-and-other-pdx-games-on-linux.1463776)) |
| Display | Xvfb plus Mesa's software OpenGL (llvmpipe). CK2 on Linux uses OpenGL 2.1 (same thread) |
| Game | Steam app 203770. Depots per [SteamDB](https://steamdb.info/app/203770/depots), not verified: `203771` CKIIMain (shared content), `210909` Linux binaries. DLC depots are optional for a smoke. Download once with DepotDownloader and Steam QR login on the host, which needs direct internet. Path in env `CK2_GAME_DIR`, outside any checkout |
| User dir | env `CK2_USER_DIR` (CK2 on Linux uses `~/.paradoxinteractive/Crusader Kings II`; `tools/install.sh` assumes that) |
| Libraries | whatever `ldd` on the binary lists. Forum reports name `libGLU.so.1` and `libtbb.so.2` |
| Steam | as for Windows: unknown whether the binary starts without a Steam client. If it refuses, the runner needs a Steam client, or the host isn't usable |
| Time | expect slow boots under software rendering; budget 15 minutes a job until measured |

To verify first: the binary starts under `xvfb-run`, reaches the main menu (screenshot with
`xwd` or `import`), and writes `error.log`. Only then write `tools/smoke.sh`, mirroring
`smoke.ps1`.

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

Script files only (no binaries), CK2 3.3.3, are cached in the Claude project's shared files and
unpacked into `vanilla/` by the session hook. They are enough for lint, cross-references and CWTools, not for running the game.
See the `game-files` skill.
