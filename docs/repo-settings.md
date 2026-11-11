# GitHub repo settings

Settings that live on GitHub, not in files. Claude sessions can't change them (the proxy blocks settings writes), so the owner applies them. Keep this file in step with what is set.

## General > Pull Requests

- [ ] Allow merge commits: off
- [ ] Allow squash merging: off
- [ ] Allow rebase merging: on (the only merge method)
- [ ] Always suggest updating pull request branches: on
- [ ] Allow auto-merge: on
- [ ] Automatically delete head branches: on

## General > Features

- [ ] Wikis: off (docs live in `docs/`)
- [ ] Projects: off unless used

## Rules > Rulesets > New branch ruleset

Name `main`, enforcement Active, target: Include default branch. Bypass list: Repository admin (for emergencies only).

- [ ] Restrict deletions
- [ ] Block force pushes
- [ ] Require linear history
- [ ] Require a pull request before merging, required approvals 0 (a solo owner can't approve their own PR)
- [ ] Require status checks to pass: add `lint`; tick "Require branches to be up to date before merging"

## Advanced Security

- [ ] Dependabot alerts: on (alerts only; version updates come from Renovate, configured in `renovate.json`)
- [ ] Secret scanning and push protection: on (free for public repos)

## Renovate

The Renovate app is installed. `renovate.json` updates GitHub Actions, the `.cwtools` submodule, and the DepotDownloader and CWTools CLI versions pinned in `tools/cloud_setup.sh`. Close Renovate's onboarding PR (#2) once `renovate.json` is on `main`, if it hasn't closed itself.

## Labels

Created 2026-11-11 by Claude: `needs-in-game-test`, `test-report`, `tooling`, `game-files`, `blocked-on-user`, `save-breaking`, `mp-checksum`.
