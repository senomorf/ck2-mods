# ck2-mods

Crusader Kings II mods, built with Claude Code in cloud sessions and tested on a real install.

## Design principles

Historical immersion is the main reason these mods exist (owner, 2026-11-14). Every mod is designed in this order:

1. **History.** How did the thing work in reality: who did it, what it needed, what it cost, what it depended on? Cite sources, and label anything unverified.
2. **The game.** What CK2 already models, what its script can and cannot do (checked in `vanilla/`, `.cwtools/` and, where it matters, on the live test box), and which existing rules and restrictions the mod can build on.
3. **Play.** Keep it balanced and interesting, in single player and multiplayer: both sides of a deal pay something, no free power, few clicks, clear numbers on screen.

Where realism and play pull apart, the mod's README says which way it went and why. A design starts in the mod's README (or its tracking issue) before any script.

## Layout

| Path | What |
| --- | --- |
| `mods/<folder>/`, `mods/<folder>.mod` | One mod and its launcher descriptor |
| `mods/_template/` | Copied by `tools/new_mod.py` |
| `tools/` | Scaffold, lint, package, install, error-log filter (Python stdlib) |
| `tests/` | Tests for the tools |
| `docs/ck2-notes.md` | Confirmed CK2 facts, with sources |
| `.claude/` | Agent settings, session-start hook, skills |
| `vanilla/` | Game files for reference; gitignored, never committed |

## Start a mod

```
python3 tools/new_mod.py my_mod --prefix mm --name "My Mod"
python3 tools/lint.py my_mod
```

## Test on your PC

1. Clone this repo.
2. Link the mod into the game's mod folder:
   - Windows: `powershell -ExecutionPolicy Bypass -File tools\install.ps1 my_mod`
   - Linux/macOS: `tools/install.sh my_mod` (pass the CK2 user folder as a second argument if the default is wrong)
3. Enable it in the launcher. After a `git pull`, restart the game; re-run the install only if the `.mod` file changed.
4. Report results with the **Test report** issue form, including lines from `python3 tools/errorlog.py <path to logs/error.log> my_mod`.

Default user folders are assumptions to check on first install: `Documents/Paradox Interactive/Crusader Kings II` (Windows, macOS) and `~/.paradoxinteractive/Crusader Kings II` (Linux).

## Claude cloud sessions

Use the `ck2-mod-dev` environment. Its setup script is one line that calls the repo's own script, so changes to setup go through PRs here:

```bash
[ -f ck2-mods/tools/cloud_setup.sh ] && bash ck2-mods/tools/cloud_setup.sh; exit 0
```

`tools/cloud_setup.sh` installs DepotDownloader, .NET 10 and the CWTools CLI. New containers run the version on `main`. The session-start hook in `.claude/hooks/` then provides:

| Path | Source | In git? |
| --- | --- | --- |
| `.cwtools/` | [cwtools-ck2-config](https://github.com/cwtools/cwtools-ck2-config) rule files (also used by the VS Code extension) | Submodule |
| `reference/emf/` | [EMF](https://github.com/EMFTeam/EMF) source, for working examples | No |
| `vanilla/` | Your game files, from the project cache (below) | No |

On your PC, run `git submodule update --init` after cloning so CWTools in VS Code picks up `.cwtools/`.

## Game files

Agents read the game's own script files to copy real syntax. They are downloaded once from your Steam account and cached in the Claude project's shared files, never in git:

1. In a `ck2-mod-dev` thread, ask Claude to fetch the game files.
2. Claude runs `tools/steam_fetch_vanilla.py --qr` and posts a QR code. Scan it in the Steam mobile app (Steam Guard > scan QR). No password is typed anywhere.
3. [DepotDownloader](https://github.com/SteamRE/DepotDownloader) downloads only `common`, `decisions`, `events`, `history`, `localisation`, `interface`, map text files and top-level text files.
4. The result is `/mnt/project-files/ck2-vanilla/ck2-game-files.zip` plus a JSON manifest. Every later session unpacks it into `vanilla/` automatically.

The Steam session token is deleted after the run unless you ask Claude to keep it (`--keep-login`), which allows re-downloads without a new scan. CK2 no longer gets patches, so one download should last.

Fallback without Steam: zip those folders from your install (Steam > Crusader Kings II > Manage > Browse local files) and send the zip to Claude to save at the same path.

## Multiplayer

Every player needs the same version of the mod, since mods change the game checksum. Install from the same GitHub release (tags `<mod>-v<version>`, built by CI) and compare the checksum in the launcher before hosting.

## Contributing

Rebase workflow with protected `main`; see the Git workflow section of `CLAUDE.md` and `docs/repo-settings.md`.
