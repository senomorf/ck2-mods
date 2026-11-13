#!/usr/bin/env python3
"""In-game test harness for tools/campaign.sh (roadmap #13, step 3).

install MOD DEST   copy mods/MOD to DEST (the game's mod folder entry), add a
                   `log = "CK2TEST fired <id>"` line to every event's immediate
                   block, and add the tests in tests/game/MOD/ if there are any.
report MOD LOG     read the CK2TEST lines in LOG (the run's game.log), print a
                   report, and exit 1 when a test failed, the tests did not
                   finish, or (for a mod with tests) one of its events never fired.

The `log` effect writes to game.log when the game runs with -debugscripts or
-scriptlog (vanilla/ChangeLog.txt). Test events write their own lines:
  CK2TEST pass <name> / CK2TEST fail <name>   one check
  CK2TEST done                                 the tests finished
Files keep their bytes: CK2 script is Windows-1252, read and written as latin-1.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVENT_KEY = re.compile(r"[a-z_]*_event$")
MARK = "CK2TEST"


def scan(text: str):
    """Yield (depth, start, end, kind) tokens: kind is 'word', '=', '{', '}' or 'str'.

    Comments (# to end of line) are skipped. depth is the depth before the token."""
    i, n, depth = 0, len(text), 0
    while i < n:
        c = text[i]
        if c == "#":
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif c.isspace():
            i += 1
        elif c == '"':
            j = text.find('"', i + 1)
            j = n - 1 if j < 0 else j
            yield depth, i, j + 1, "str"
            i = j + 1
        elif c == "{":
            yield depth, i, i + 1, "{"
            depth += 1
            i += 1
        elif c == "}":
            depth -= 1
            yield depth, i, i + 1, "}"
            i += 1
        elif c in "=<>":
            yield depth, i, i + 1, "="
            i += 1
        else:
            j = i
            while j < n and not text[j].isspace() and text[j] not in '{}=<>#"':
                j += 1
            yield depth, i, j, "word"
            i = j


def events(text: str):
    """(id, open brace of immediate or None, close brace of the event) for each event block."""
    toks = list(scan(text))
    out = []
    k = 0
    while k + 2 < len(toks):
        d, s, e, kind = toks[k]
        if d == 0 and kind == "word" and EVENT_KEY.match(text[s:e]) and toks[k + 1][3] == "=" and toks[k + 2][3] == "{":
            ev_id, immediate, m = None, None, k + 3
            while m < len(toks) and not (toks[m][0] == 0 and toks[m][3] == "}"):
                d2, s2, e2, k2 = toks[m]
                if d2 == 1 and k2 == "word" and m + 2 < len(toks) and toks[m + 1][3] == "=":
                    key = text[s2:e2]
                    if key == "id" and toks[m + 2][3] in ("word", "str"):
                        ev_id = text[toks[m + 2][1]:toks[m + 2][2]].strip('"')
                    elif key == "immediate" and toks[m + 2][3] == "{":
                        immediate = toks[m + 2][1]
                m += 1
            if ev_id and m < len(toks):
                out.append((ev_id, immediate, toks[m][1]))
            k = m + 1
        else:
            k += 1
    return out


def instrument(text: str) -> tuple[str, list[str]]:
    """Add the fired line to every event; return the new text and the event ids."""
    found = events(text)
    for ev_id, immediate, close in sorted(found, key=lambda f: -(f[1] if f[1] is not None else f[2])):
        line = f'log = "{MARK} fired {ev_id}"'
        if immediate is not None:
            text = text[: immediate + 1] + f"\n\t\t{line} # tools/harness.py\n" + text[immediate + 1 :]
        else:
            text = text[:close] + f"\timmediate = {{ {line} }} # tools/harness.py\n" + text[close:]
    return text, [f[0] for f in found]


def mod_events(mod: str) -> list[str]:
    ids: list[str] = []
    for f in sorted((REPO / "mods" / mod / "events").glob("*.txt")):
        ids += [e[0] for e in events(f.read_text(encoding="latin-1"))]
    return ids


def install(mod: str, dest: Path) -> int:
    src = REPO / "mods" / mod
    if not src.is_dir():
        print(f"harness: no mods/{mod}", file=sys.stderr)
        return 2
    if dest.is_symlink() or dest.is_file():
        dest.unlink()
    elif dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)
    count = 0
    for f in sorted((dest / "events").glob("*.txt")):
        text, ids = instrument(f.read_text(encoding="latin-1"))
        f.write_text(text, encoding="latin-1", newline="")
        count += len(ids)
    tests = REPO / "tests" / "game" / mod
    added = 0
    if tests.is_dir():
        for f in sorted(p for p in tests.rglob("*") if p.is_file()):
            target = dest / f.relative_to(tests)
            if target.exists():
                print(f"harness: tests/game/{mod}/{f.relative_to(tests)} would replace a mod file", file=sys.stderr)
                return 2
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            added += 1
    print(f"harness: {mod} copied to {dest}, {count} event(s) instrumented, {added} test file(s) added")
    return 0


def report(mod: str, log: Path) -> int:
    lines = log.read_text(encoding="latin-1", errors="replace").splitlines() if log.is_file() else []
    fired: dict[str, int] = {}
    passes: dict[str, int] = {}
    fails: dict[str, int] = {}
    done = False
    pat = re.compile(re.escape(MARK) + r" (fired|pass|fail|done)\b ?(.*)")
    for line in lines:
        m = pat.search(line)
        if not m:
            continue
        kind, rest = m.group(1), m.group(2).strip()
        if kind == "fired":
            fired[rest] = fired.get(rest, 0) + 1
        elif kind == "pass":
            passes[rest] = passes.get(rest, 0) + 1
        elif kind == "fail":
            fails[rest] = fails.get(rest, 0) + 1
        else:
            done = True
    has_tests = (REPO / "tests" / "game" / mod).is_dir()
    ids = mod_events(mod)
    unfired = [i for i in ids if i not in fired]
    print(f"In-game tests: {mod} ({'tests in tests/game/' + mod if has_tests else 'no tests; events only counted'})")
    print(f"events fired: {len(ids) - len(unfired)} of {len(ids)}")
    for i in ids:
        print(f"  {i}: {fired.get(i, 0)}")
    for name, n in sorted(passes.items()):
        print(f"pass: {name}" + (f" (x{n})" if n > 1 else ""))
    for name, n in sorted(fails.items()):
        print(f"FAIL: {name}" + (f" (x{n})" if n > 1 else ""))
    problems = []
    if fails:
        problems.append(f"{len(fails)} check(s) failed")
    if has_tests and not done:
        problems.append("the tests did not log CK2TEST done")
    if has_tests and unfired:
        problems.append("never fired: " + ", ".join(unfired))
    print("result: " + ("; ".join(problems) if problems else "ok"))
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "install":
        return install(argv[1], Path(argv[2]))
    if len(argv) == 3 and argv[0] == "report":
        return report(argv[1], Path(argv[2]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
