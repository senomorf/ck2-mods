---
name: test-round
description: Hand a CK2 mod change to the user for in-game testing, and turn their report or error.log into fixes.
---

# In-game test round

The agent cannot run CK2. Each change goes to the user as a short, concrete test.

## Handing over

Put this in the PR body (or a comment), filled in for the change:

```
### Test in game
Install: tools/install.ps1 <folder>   (or tools/install.sh <folder>), enable in launcher
Setup: <bookmark/character, console commands e.g. `event <prefix>.1`, `debug_mode`>
Expect:
- [ ] <observable result 1>
- [ ] <observable result 2>
Save check: load an existing save with the mod on; it loads and <thing> works
DLC (CI plays without any):
- [ ] <behaviour that depends on a DLC, e.g. "with Conclave: the council vote shows">, or "none"
Multiplayer (CI cannot host a game):
- [ ] Main menu label reads <code from the smoke report>, the same on every player's machine
- [ ] <behaviour that differs in multiplayer, e.g. "the requester sees the ally's answer">, or "none"
Then send: logs/error.log, or the lines from `python3 tools/errorlog.py error.log <folder>`
If something went wrong: add `-scriptlog` to CK2's Steam launch options, play to the problem again,
and send logs/game.log too: it has the mod's own `<prefix>:` lines saying what each step did
```

Keep it under ten steps and each expectation observable on screen.

### DLC and multiplayer

CI covers neither, so these go to the owner (owner's choice, 2026-11-13: tests stay DLC-free).
The runner's game has no Steam client, so it loads no DLC: a save that needs one is refused, and
Multiplayer is greyed out (#21 item 10).

- **DLC.** List what the change does differently with a DLC: a trigger like `has_dlc`, content
  gated by a DLC's game rule or mechanic (societies, artifacts, Conclave council), or vanilla files
  that only matter with a DLC. Name the DLC and what to look for. If nothing depends on one, write
  "none" so the owner knows it was checked.
- **Multiplayer.** Every player needs the same release: the smoke job's report gives the main menu's
  version label (e.g. `3.3.5.1 (SOHY)` for vanilla) with and without the mod, so put the expected
  code in the checklist, and label the PR `mp-checksum` when it differs from vanilla's. List what
  only multiplayer shows: events or decisions between two human players, anything that uses
  `ai = no` or the player's own character, and an out-of-sync after the mod's events fire.

## Handling the report

1. If the user sent an error.log (an upload or pasted text), run `python3 tools/errorlog.py <file> <folder>`.
2. Map each line to a file and construct; check the syntax with the `ck2-syntax` skill before changing it.
3. Fix, lint, push, and post a new, shorter test list for only what changed.
4. Record anything the test confirmed in `docs/ck2-notes.md` with "confirmed in game, <date>, CK2 <version>".
