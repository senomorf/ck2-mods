# ck2-mods

Crusader Kings II mods, built with Claude Code in cloud sessions and tested on a real install.

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

Use the `ck2-mod-dev` environment. Paste `tools/cloud_setup.sh` into its Setup script field; it installs .NET 9 and the CWTools CLI. Everything else comes from the session-start hook in `.claude/hooks/`, which runs in any environment:

| Path | Source | In git? |
| --- | --- | --- |
| `.cwtools/` | [cwtools-ck2-config](https://github.com/cwtools/cwtools-ck2-config) rule files (also used by the VS Code extension) | Submodule |
| `reference/emf/` | [EMF](https://github.com/EMFTeam/EMF) source, for working examples | No |
| `vanilla/` | Your game files, if provided (below) | No |

On your PC, run `git submodule update --init` after cloning so CWTools in VS Code picks up `.cwtools/`.

## Game files for cloud sessions

Agents need the game's script files to copy real syntax. Zip these folders from the install (Steam > Crusader Kings II > Manage > Browse local files): `common`, `decisions`, `events`, `history`, `localisation`, `interface`. The zip is stored outside git, at `/mnt/project-files/ck2-vanilla/ck2-game-files.zip` in the Claude project, and the session-start hook unpacks it into `vanilla/`.

## Multiplayer

Every player needs the same commit of the mod. Mods change the game checksum, so compare it in the launcher before hosting.
