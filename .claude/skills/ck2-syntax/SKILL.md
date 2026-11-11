---
name: ck2-syntax
description: Look up real CK2 script syntax (effects, triggers, scopes, decision and event blocks) in vanilla/ or reference mods before writing or changing any CK2 script.
---

# Finding real CK2 syntax

CK2 script has no formal spec, and guessed syntax fails silently in game. Ground every new construct in a working example.

1. Check `docs/ck2-notes.md` first. If the construct is recorded there with a source, use it.
2. If `vanilla/` exists, grep it. Search the exact keyword with context:
   - `grep -rn --include=*.txt -B3 -A12 "spawn_fleet" vanilla/decisions vanilla/events | head -80`
   - Decisions: `vanilla/decisions/`; targeted decisions use `targeted_decisions = { ... }` blocks.
   - Events: `vanilla/events/`; modifiers: `vanilla/common/event_modifiers/`; on_actions: `vanilla/common/on_actions/`.
   - Read files as Windows-1252 if a tool complains about UTF-8.
3. If `vanilla/` is missing, use the references in `docs/references.md` (EMF on GitHub, CK2 wiki Commands, Conditions and Scopes pages), fetched, not recalled. Tell the user the game files are missing, since vanilla is the authority for their game version.
4. Never present syntax from memory as confirmed. If you could not find an example, say so in the PR and mark the line with `# UNVERIFIED:` and a short reason.
5. When you confirm something non-obvious, add one line to `docs/ck2-notes.md`: the construct, what it does, and the source file or URL.
