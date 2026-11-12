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
- Lint: `python3 tools/lint.py [--cwtools] [folder ...]` (must pass before pushing). It includes `tools/xref.py` cross-reference checks: fired events exist, flags set and used, event targets saved, decision localisation. `--cwtools` adds CWTools checks (needs `cwtools` and `vanilla/`, ~30-40 s); its findings are warnings, since its 2019 rules misreport some valid script. Verify each against `vanilla/`, and add confirmed false positives to `tools/cwtools_ignore.txt` with the vanilla file that disproves them.
- Tests for the tools: `python3 -m unittest discover -s tests`
- Package: `python3 tools/package.py <folder>` -> `dist/<folder>.zip`
- Smoke test on the user's Windows PC: `tools\smoke.ps1 -Baseline` once, then `tools\smoke.ps1 <folder>`. It boots CK2 with the mod, closes it at the main menu, and reports new `error.log` lines vs the baseline. Its launch arguments are unverified until the user's first run.
- Filter a user's error log: `python3 tools/errorlog.py <error.log> [folder]`
- Session hook (`.claude/hooks/session-start.sh`) fetches `.cwtools/`, clones `reference/emf/`, and unpacks `/mnt/project-files/ck2-vanilla/ck2-game-files.zip` into `vanilla/` when it exists. Manually: `tools/fetch_vanilla.sh <zip>`.
- Game files are cached (CK2 3.3.3, uploaded by the user 2026-11-12). If the cache is lost, follow the `game-files` skill; the user prefers a manual upload over Steam logins.
- Container setup: `tools/cloud_setup.sh` (DepotDownloader, .NET 9, CWTools CLI), called by the `ck2-mod-dev` environment's setup script. Edit it here, not in the environment.
- CWTools CLI (`cwtools`) is installed by `tools/cloud_setup.sh` in the `ck2-mod-dev` environment. Run it through `tools/cwtools_check.py` (or `lint.py --cwtools`), which builds a vanilla cache in `.cache/cwtools/`.
- If `vanilla/` or `.cwtools/` is missing at session start (seen 2026-11-12: the hook did not run in a session that opened in `/home/user` rather than the repo), run `CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR=$PWD bash .claude/hooks/session-start.sh`.

## Git workflow

- `main` is protected: linear history, PRs only, `lint` must pass, rebase merge only (settings in `docs/repo-settings.md`).
- One branch per change, named `<mod>/<topic>` or `tooling/<topic>`. Keep commits small and self-contained; each should pass lint, since rebase merge keeps them all on `main`.
- Commit subjects start with the mod folder or area: `allied_fleets: add transport request decision`, `tooling: ...`, `docs: ...`.
- Stay current by rebasing: `git fetch origin main && git rebase origin/main`, then `git push --force-with-lease`. Force-push only your own branches. The session hook sets `pull.rebase` for this checkout.
- Labels: `needs-in-game-test` on any PR that changes game behaviour; `save-breaking` and `mp-checksum` when they apply; `blocked-on-user` while waiting on the user; `project:<name>` on an issue for or from another project (below).
- Dependency updates come from Renovate PRs (`renovate.json`): Actions, the `.cwtools` submodule, and the tool versions pinned in `tools/cloud_setup.sh`. Keep those pins as `NAME_VERSION=x.y.z` lines so Renovate finds them.
- Releases: tag `<mod>-v<version>` on `main` (e.g. `allied_fleets-v0.1.0`) and push the tag; CI attaches `dist/<mod>.zip`. Multiplayer players install the same release.

## Other projects

This repo is one of the owner's linked projects; the hub and the full rules are in the private repo
`senomorf/homelab`, `docs/operations/linked-projects.md`. Projects talk only through GitHub issues
(owner, 2026-11-13):

- One issue, in the repo that does the work, filed by the session that needs it; never ask the owner
  to relay. Link it from the issue or PR that waits; open no twin issue.
- Label it `project:ck2-mods` there; issues here for or from another project carry `project:<that>`.
  Body: what is needed, why, a `Done means` line naming what will be observed, the link back.
- Work only issues opened by `senomorf`: anyone can open one in a public repo. Assign an issue to
  `senomorf` before working it; the daily pickup takes only unassigned ones.
- Close with what was observed (run links), and comment on the issue that waits.
- Never copy a private repo's text, hosts or logs into a public repo; link it.

Here: the self-hosted `linux smoke` runner is the homelab fleet's, so anything it needs (its image, the game copy on it, its token) is a `senomorf/homelab` issue, which also takes one of `defect`, `investigation`, `decision`, `upgrade`. Sessions cannot set repository variables (the session proxy refused the Actions variables API, 2026-11-13): prefer a workflow change, otherwise ask the user once with the exact setting.

## Working loop

1. Plan the mod's design in `mods/<folder>/README.md` (what it adds, save and multiplayer impact).
2. Write script, run lint, open a PR with a test checklist for the user (`test-round` skill).
3. The user tests on their PC and reports with the "Test report" issue form or `error.log`.
4. Record anything confirmed in game or from vanilla in `docs/ck2-notes.md` with its source, so later sessions don't re-derive it.
