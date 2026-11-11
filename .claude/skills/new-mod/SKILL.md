---
name: new-mod
description: Start a new CK2 mod in this repo: pick folder and prefix, scaffold from the template, write its design README, and open a draft PR.
---

# Starting a new mod

1. Agree the folder name (lowercase, underscores) and a 2-8 character prefix not used by any `mods/*/PREFIX` or by vanilla (`grep -rl "namespace = <prefix>$" vanilla/events` should find nothing).
2. Run `python3 tools/new_mod.py <folder> --prefix <prefix> --name "<Display Name>"`.
3. Write `mods/<folder>/README.md`:
   - What the mod adds, in player terms.
   - Files it adds and any vanilla file it overrides (ideally none).
   - Save compatibility: does it load into an existing save? Why.
   - Multiplayer: all players need the same version; checksum changes.
   - Open design questions for the user.
4. Delete the template's example event and its localisation if the mod doesn't need them.
5. Run `python3 tools/lint.py <folder>`, commit on a branch, open a draft PR. The PR body includes the test checklist from the `test-round` skill.
