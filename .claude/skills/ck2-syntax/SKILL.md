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
3. Check the CWTools rules for parameters and allowed scopes:
   - `grep -rn -A30 "alias\[effect:<name>\]" .cwtools/` (effects), `alias\[trigger:<name>\]` (triggers), `.cwtools/scopes.cwt`, `.cwtools/modifiers.cwt`.
   - Lines starting `##` are rules (cardinality, scope); `###` are descriptions. The rules date from 2019; vanilla wins if they disagree.
4. Find a working example in EMF: `grep -rn --include=*.txt -B3 -A12 "<keyword>" reference/emf/EMF | head -80`.
5. If none of these exist (hook failed), fetch the pages in `docs/references.md`. Tell the user which sources were missing, since vanilla is the authority for their game version.
6. Never present syntax from memory as confirmed. If you could not find an example, say so in the PR and mark the line with `# UNVERIFIED:` and a short reason.
7. When you confirm something non-obvious, add one line to `docs/ck2-notes.md`: the construct, what it does, and the source file or URL.
