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
Then send: logs/error.log, or the lines from `python3 tools/errorlog.py error.log <folder>`
```

Keep it under ten steps and each expectation observable on screen.

## Handling the report

1. If the user sent an error.log (an upload or pasted text), run `python3 tools/errorlog.py <file> <folder>`.
2. Map each line to a file and construct; check the syntax with the `ck2-syntax` skill before changing it.
3. Fix, lint, push, and post a new, shorter test list for only what changed.
4. Record anything the test confirmed in `docs/ck2-notes.md` with "confirmed in game, <date>, CK2 <version>".
