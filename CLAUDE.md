# ck2-mods

Workspace for Crusader Kings II mods. Each mod is `mods/<folder>/` plus its launcher descriptor `mods/<folder>.mod`. Shared tooling is in `tools/` (Python standard library only).

## Hard limits

- The game cannot run in a cloud session. Every behaviour claim about a change is unverified until the user tests it in game. Say so in PRs and replies.
- `vanilla/` holds the game's own files (Paradox content), and `reference/` other people's mods. Read and grep it freely; never commit it, quote large parts of it into the repo, or copy vanilla files into a mod. Copy patterns, not files.
- Never invent script syntax. Before using an effect, trigger, scope or block you have not already seen in this repo, check it against the sources below and cite the file in the PR. Use the `ck2-syntax` skill.

## Syntax sources, most authoritative first

1. `vanilla/` - the game's own files, from the cache the session hook unpacks (`game-files` skill).
2. `.cwtools/*.cwt` - CWTools rules for CK2 (git submodule, last updated 2019): every effect, trigger, scope and modifier with its parameters. E.g. `grep -n -A30 "alias\[effect:spawn_fleet\]" .cwtools/effects.cwt`.
3. `reference/emf/` - EMF mod source (gitignored, cloned by the session hook): working examples. Its `EMF+Vanilla/` folder holds vanilla-derived overrides.
4. `docs/references.md` - CK2 wiki pages, fetched rather than recalled.

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
- Session hook (`.claude/hooks/session-start.sh`) fetches `.cwtools/`, clones `reference/emf/`, and unpacks `/mnt/project-files/ck2-vanilla/ck2-game-files.zip` into `vanilla/` when it exists. Manually: `tools/fetch_vanilla.sh <zip>`.
- Download game files from Steam (user scans a QR code): `python3 tools/steam_fetch_vanilla.py --qr`. Follow the `game-files` skill.
- Container setup: `tools/cloud_setup.sh` (DepotDownloader, .NET 9, CWTools CLI), called by the `ck2-mod-dev` environment's setup script. Edit it here, not in the environment.
- CWTools CLI (`cwtools`) is installed by `tools/cloud_setup.sh` in the `ck2-mod-dev` environment. Its CK2 support is partial and it is not yet wired into lint: run `cwtools --help` and try it on a mod before relying on it.

## Git workflow

- `main` is protected: linear history, PRs only, `lint` must pass, rebase merge only (settings in `docs/repo-settings.md`).
- One branch per change, named `<mod>/<topic>` or `tooling/<topic>`. Keep commits small and self-contained; each should pass lint, since rebase merge keeps them all on `main`.
- Commit subjects start with the mod folder or area: `allied_fleets: add transport request decision`, `tooling: ...`, `docs: ...`.
- Stay current by rebasing: `git fetch origin main && git rebase origin/main`, then `git push --force-with-lease`. Force-push only your own branches. The session hook sets `pull.rebase` for this checkout.
- Labels: `needs-in-game-test` on any PR that changes game behaviour; `save-breaking` and `mp-checksum` when they apply; `blocked-on-user` while waiting on the user.
- Releases: tag `<mod>-v<version>` on `main` (e.g. `allied_fleets-v0.1.0`) and push the tag; CI attaches `dist/<mod>.zip`. Multiplayer players install the same release.

## Working loop

1. Plan the mod's design in `mods/<folder>/README.md` (what it adds, save and multiplayer impact).
2. Write script, run lint, open a PR with a test checklist for the user (`test-round` skill).
3. The user tests on their PC and reports with the "Test report" issue form or `error.log`.
4. Record anything confirmed in game or from vanilla in `docs/ck2-notes.md` with its source, so later sessions don't re-derive it.
