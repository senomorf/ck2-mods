# ck2-mods

Workspace for Crusader Kings II mods. Each mod is `mods/<folder>/` plus its launcher descriptor `mods/<folder>.mod`. Shared tooling is in `tools/` (Python standard library only).

## Hard limits

- The game cannot run in a cloud session. Every behaviour claim about a change is unverified until the user tests it in game. Say so in PRs and replies.
- `vanilla/` holds the game's own files (Paradox content). Read and grep it freely; never commit it, quote large parts of it into the repo, or copy vanilla files into a mod. Copy patterns, not files.
- Never invent script syntax. Before using an effect, trigger, scope or block you have not already seen in this repo, find a real example in `vanilla/` (or EMF, see `docs/references.md`) and cite the file in the PR. Use the `ck2-syntax` skill.

## Conventions

- Every mod has a 2-8 character prefix in `mods/<folder>/PREFIX`. Use it for file names (`<prefix>_events.txt`), event namespace (`namespace = <prefix>`, ids `<prefix>.N`), localisation keys, modifiers, decisions and flags. This keeps mods from colliding with vanilla and each other.
- Add new content in new files. Override a vanilla file only when unavoidable, and note it in the mod's README, since it breaks compatibility with other mods and game updates.
- Files are Windows-1252 with LF line endings. Keep script ASCII where possible.
- Localisation: `localisation/<prefix>_*.csv`, semicolon-separated, header `#CODE;ENGLISH;FRENCH;GERMAN;;SPANISH;;;;;;;;;x`, each line ends with `;x`.
- Prefer changes that keep existing saves loading: add, don't remove or rename. Note save impact in the PR.

## Commands

- New mod: `python3 tools/new_mod.py <folder> --prefix <p> --name "Name"`
- Lint: `python3 tools/lint.py [folder ...]` (must pass before pushing)
- Tests for the tools: `python3 -m unittest discover -s tests`
- Package: `python3 tools/package.py <folder>` -> `dist/<folder>.zip`
- Filter a user's error log: `python3 tools/errorlog.py <error.log> [folder]`
- Game files: the session-start hook unpacks `/mnt/project-files/ck2-vanilla/ck2-game-files.zip` into `vanilla/` when it exists. Manually: `tools/fetch_vanilla.sh <zip>`.

## Working loop

1. Plan the mod's design in `mods/<folder>/README.md` (what it adds, save and multiplayer impact).
2. Write script, run lint, open a PR with a test checklist for the user (`test-round` skill).
3. The user tests on their PC and reports with the "Test report" issue form or `error.log`.
4. Record anything confirmed in game or from vanilla in `docs/ck2-notes.md` with its source, so later sessions don't re-derive it.
