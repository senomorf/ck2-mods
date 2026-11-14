#!/usr/bin/env python3
"""In-game test harness for tools/campaign.sh (roadmap #13, step 3; tracing: #38, step 1).

install MOD DEST   copy mods/MOD to DEST (the game's mod folder entry), add a trace line
                   (below) to every event, event option, decision effect and scripted effect,
                   and add the tests in tests/game/MOD/ if there are any.
report MOD LOG     read the CK2TEST lines in LOG (the run's game.log), print a report, and
                   exit 1 when a test failed, the tests did not finish, or (for a mod with
                   tests) one of its events never fired, an option was never chosen or a
                   scripted effect never ran. Decisions are only counted: tests cannot take one.

Trace lines, each written by a `log` effect the copy gains:
  CK2TEST fired <event id> [root=<id>]           an event's immediate block ran
  CK2TEST chose <event id> <option> [root=<id>]  an option ran (<option> is its name, or
                                                 option<N> when it has none)
  CK2TEST took <decision> [root=<id>] [from=<id>]  a decision's effect ran
  CK2TEST ran <scripted effect>                  a scripted effect ran
root= and from= are character ids ([Root.GetID], [From.GetID]), written only where that scope
is a character: character, letter, narrative, long character and diplomatic response events;
decisions, society and targeted decisions (from= for targeted and title decisions, whose
taker is FROM). Elsewhere ROOT may be a province or a title.

The `log` effect writes to game.log when the game runs with -debugscripts or -scriptlog
(vanilla/ChangeLog.txt); each line reads `[effectimplementation.cpp:N]: EVENT [<date>]:<text>`.
Test events write their own lines:
  CK2TEST pass <name>[: <details>]            one check; the name is the text before the first
  CK2TEST fail <name>[: <details>]            ': ', so details (values, ids) can follow it
  CK2TEST done                                 the tests finished
A check that a file under tests/game/MOD/ names but that never reports fails the run (#38, step 2).

tests/game/MOD/log_checks.txt holds checks on the counts above, one per line ('#' at the start
or after a space starts a comment):
  count KIND NAME OP N                    KIND is fired, chose, took, ran, pass or fail, NAME as
  count KIND NAME OP count KIND NAME      the trace or check writes it; OP is == != >= <= > <
  count line TEXT OP N                    game.log lines that contain TEXT (a mod's own log)
e.g. `count fired afl.2 == count chose afl.1 EVTOPTA_afl_1`.
Files keep their bytes: CK2 script is Windows-1252, read and written as latin-1.
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
EVENT_KEY = re.compile(r"[a-z_]*_event$")
DECISIONS_KEY = re.compile(r"[a-z_]*decisions$")
# Where ROOT is a character: vanilla/events (character_event and its kinds) and
# vanilla/decisions (decisions, society_decisions, targeted_decisions, targetted_decisions).
CHARACTER_EVENTS = {"character_event", "letter_event", "narrative_event", "long_character_event", "diploresponse_event"}
ROOT_DECISIONS = {"decisions", "society_decisions", "targeted_decisions", "targetted_decisions"}
FROM_DECISIONS = {"targeted_decisions", "targetted_decisions", "title_decisions"}
NOTE = " # tools/harness.py"
MARK = "CK2TEST"
SAVE_CHECKS = Path("save_checks.txt")
LOG_CHECKS = Path("log_checks.txt")
NOT_COPIED = {SAVE_CHECKS, LOG_CHECKS}  # read by the tools, not by the game
OPS = {"==": lambda a, b: a == b, "!=": lambda a, b: a != b, ">=": lambda a, b: a >= b,
       "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, "<": lambda a, b: a < b}


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


def blocks(text: str, toks: list, lo: int, hi: int, depth: int) -> list[tuple[str, int, int]]:
    """(key, index of its '{', index of its '}') for each `key = { ... }` at depth in toks[lo:hi]."""
    out = []
    k = lo
    while k + 2 < hi:
        d, s, e, kind = toks[k]
        if d == depth and kind in ("word", "str") and toks[k + 1][3] == "=" and toks[k + 2][3] == "{":
            m = k + 3
            while m < hi and not (toks[m][0] == depth and toks[m][3] == "}"):
                m += 1
            out.append((text[s:e].strip('"'), k + 2, m))
            k = m + 1
        else:
            k += 1
    return out


def value(text: str, toks: list, lo: int, hi: int, depth: int, key: str) -> str | None:
    """The word or string after `key =` at depth in toks[lo:hi]."""
    for k in range(lo, hi - 2):
        d, s, e, kind = toks[k]
        if d == depth and kind == "word" and text[s:e] == key and toks[k + 1][3] == "=" and toks[k + 2][3] in ("word", "str"):
            return text[toks[k + 2][1] : toks[k + 2][2]].strip('"')
    return None


def events(text: str) -> list[dict]:
    """Each event block: kind, id, the character offsets of its immediate's '{' (or None) and of
    its closing '}', and its options as (label, offset of the option's '{')."""
    toks = list(scan(text))
    out = []
    for kind, o, c in blocks(text, toks, 0, len(toks), 0):
        if not EVENT_KEY.match(kind):
            continue
        ev_id = value(text, toks, o + 1, c, 1, "id")
        if not ev_id:
            continue
        inner = blocks(text, toks, o + 1, c, 1)
        immediate = next((toks[bo][1] for key, bo, _ in inner if key == "immediate"), None)
        options, seen = [], set()
        for n, (key, bo, bc) in enumerate((b for b in inner if b[0] == "option"), 1):
            label = value(text, toks, bo + 1, bc, 2, "name") or f"option{n}"
            if label in seen:
                label = f"{label}#{n}"
            seen.add(label)
            options.append((label, toks[bo][1]))
        out.append({"kind": kind, "id": ev_id, "immediate": immediate, "close": toks[c][1], "options": options})
    return out


def decisions(text: str) -> list[tuple[str, str, int | None]]:
    """(container, decision, offset of its effect's '{' or None) for each decision."""
    toks = list(scan(text))
    out = []
    for container, o, c in blocks(text, toks, 0, len(toks), 0):
        if DECISIONS_KEY.match(container):
            for name, do, dc in blocks(text, toks, o + 1, c, 1):
                effect = next((toks[bo][1] for key, bo, _ in blocks(text, toks, do + 1, dc, 2) if key == "effect"), None)
                out.append((container, name, effect))
    return out


def scripted_effects(text: str) -> list[tuple[str, int]]:
    toks = list(scan(text))
    return [(name, toks[o][1]) for name, o, _ in blocks(text, toks, 0, len(toks), 0)]


def _insert(text: str, edits: list[tuple[int, str]]) -> str:
    for pos, add in sorted(edits, key=lambda x: -x[0]):
        text = text[:pos] + add + text[pos:]
    return text


def instrument(text: str) -> tuple[str, list[str]]:
    """Add the trace lines to every event and option; return the new text and the event ids."""
    found = events(text)
    edits = []
    for ev in found:
        root = " root=[Root.GetID]" if ev["kind"] in CHARACTER_EVENTS else ""
        line = f'log = "{MARK} fired {ev["id"]}{root}"'
        if ev["immediate"] is not None:
            edits.append((ev["immediate"] + 1, f"\n\t\t{line}{NOTE}\n"))
        else:
            edits.append((ev["close"], f"\timmediate = {{ {line} }}{NOTE}\n"))
        for label, brace in ev["options"]:
            edits.append((brace + 1, f'\n\t\tlog = "{MARK} chose {ev["id"]} {label}{root}"{NOTE}\n'))
    return _insert(text, edits), [ev["id"] for ev in found]


def instrument_decisions(text: str) -> tuple[str, list[str]]:
    found = decisions(text)
    edits = []
    for container, name, effect in found:
        if effect is None:
            continue
        ids = (" root=[Root.GetID]" if container in ROOT_DECISIONS else "") + (" from=[From.GetID]" if container in FROM_DECISIONS else "")
        edits.append((effect + 1, f'\n\t\t\tlog = "{MARK} took {name}{ids}"{NOTE}\n'))
    return _insert(text, edits), [f[1] for f in found]


def instrument_effects(text: str) -> tuple[str, list[str]]:
    found = scripted_effects(text)
    return _insert(text, [(b + 1, f'\n\tlog = "{MARK} ran {n}"{NOTE}\n') for n, b in found]), [f[0] for f in found]


def _files(mod: Path, sub: str) -> list[Path]:
    return sorted((mod / sub).glob("*.txt"))


def inventory(mod: str) -> dict[str, list[str]]:
    """What the report expects to see traced: event ids, '<id> <option>' labels, decisions and
    scripted effects of mods/MOD."""
    src = REPO / "mods" / mod
    inv: dict[str, list[str]] = {"events": [], "options": [], "decisions": [], "effects": []}
    for f in _files(src, "events"):
        for ev in events(f.read_text(encoding="latin-1")):
            inv["events"].append(ev["id"])
            inv["options"] += [f"{ev['id']} {label}" for label, _ in ev["options"]]
    for f in _files(src, "decisions"):
        inv["decisions"] += [d[1] for d in decisions(f.read_text(encoding="latin-1")) if d[2] is not None]
    for f in _files(src, "common/scripted_effects"):
        inv["effects"] += [e[0] for e in scripted_effects(f.read_text(encoding="latin-1"))]
    return inv


def mod_events(mod: str) -> list[str]:
    return inventory(mod)["events"]


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
    count = {"event(s)": 0, "decision(s)": 0, "scripted effect(s)": 0}
    for sub, what, fn in (
        ("events", "event(s)", instrument),
        ("decisions", "decision(s)", instrument_decisions),
        ("common/scripted_effects", "scripted effect(s)", instrument_effects),
    ):
        for f in _files(dest, sub):
            text, ids = fn(f.read_text(encoding="latin-1"))
            f.write_text(text, encoding="latin-1", newline="")
            count[what] += len(ids)
    tests = REPO / "tests" / "game" / mod
    added = 0
    if tests.is_dir():
        # save_checks.txt (tools/ck2save.py) and log_checks.txt (report) are not for the game.
        for f in sorted(p for p in tests.rglob("*") if p.is_file() and p.relative_to(tests) not in NOT_COPIED):
            target = dest / f.relative_to(tests)
            if target.exists():
                print(f"harness: tests/game/{mod}/{f.relative_to(tests)} would replace a mod file", file=sys.stderr)
                return 2
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            added += 1
    traced = ", ".join(f"{n} {what}" for what, n in count.items())
    print(f"harness: {mod} copied to {dest}, traced {traced}, {added} test file(s) added")
    return 0


LINE = re.compile(r"(?:EVENT \[([0-9.]+)\]:)?" + re.escape(MARK) + r" (fired|chose|took|ran|pass|fail|done)\b ?(.*)")


def _split(rest: str) -> tuple[str, dict[str, str]]:
    """'afl.1 EVTOPTA_afl_1 root=12' -> ('afl.1 EVTOPTA_afl_1', {'root': '12'})."""
    words = rest.split()
    scopes = dict(w.split("=", 1) for w in words if w.startswith(("root=", "from=")))
    return " ".join(w for w in words if not w.startswith(("root=", "from="))), scopes


def check_name(rest: str) -> tuple[str, str]:
    """'gold moves: 40, not 50' -> ('gold moves', '40, not 50')."""
    name, _, details = rest.partition(": ")
    return name.strip(), details.strip()


def declared_checks(tests: Path) -> set[str]:
    """Check names the test files log, from `log = "CK2TEST pass|fail <name>..."` strings."""
    names: set[str] = set()
    for f in sorted(p for p in tests.rglob("*.txt") if p.relative_to(tests) not in NOT_COPIED):
        for m in re.finditer(r'log\s*=\s*"CK2TEST (?:pass|fail) ([^"]*)"', f.read_text(encoding="latin-1")):
            names.add(check_name(m.group(1))[0])
    return names


def run_log_checks(path: Path, seen: dict[str, dict[str, int]], lines: list[str]) -> list[tuple[bool, str, str]]:
    """(passed, check, what was counted) for each line of a log_checks.txt."""
    out = []

    def value(words: list[str]) -> int | None:
        if not words or words[0] not in (*seen, "line"):
            return None
        name = " ".join(words[1:])
        if words[0] == "line":
            return sum(1 for line in lines if name in line)
        return seen[words[0]].get(name, 0)

    for raw in path.read_text(encoding="latin-1").splitlines():
        line = re.split(r"(?:^|\s)#", raw, maxsplit=1)[0].strip()
        if not line:
            continue
        words = line.split()
        op = next((i for i, w in enumerate(words) if w in OPS), None)
        left = value(words[1:op]) if words[0] == "count" and op else None
        right_words = words[op + 1:] if op else []
        if len(right_words) == 1 and right_words[0].isdigit():
            right: int | None = int(right_words[0])
        elif right_words[:1] == ["count"]:
            right = value(right_words[1:])
        else:
            right = None
        if left is None or right is None or op is None:
            out.append((False, line, "not understood: count KIND NAME OP N|count KIND NAME"))
            continue
        out.append((OPS[words[op]](left, right), line, f"{left}" + ("" if right_words[0].isdigit() else f" vs {right}")))
    return out


def report(mod: str, log: Path) -> int:
    lines = log.read_text(encoding="latin-1", errors="replace").splitlines() if log.is_file() else []
    seen: dict[str, dict[str, int]] = {k: {} for k in ("fired", "chose", "took", "ran", "pass", "fail")}
    roots: dict[str, set[str]] = {}
    first: dict[str, str] = {}
    fail_details: dict[str, list[str]] = {}
    done = False
    for line in lines:
        m = LINE.search(line)
        if not m:
            continue
        date, kind, rest = m.group(1), m.group(2), m.group(3).strip()
        if kind == "done":
            done = True
            continue
        if kind in ("pass", "fail"):
            name, details = check_name(rest)
            scopes: dict[str, str] = {}
            if kind == "fail" and details and details not in fail_details.setdefault(name, []):
                fail_details[name].append(details)
        else:
            name, scopes = _split(rest)
        seen[kind][name] = seen[kind].get(name, 0) + 1
        if "root" in scopes:
            roots.setdefault(f"{kind} {name}", set()).add(scopes["root"])
        if date and f"{kind} {name}" not in first:
            first[f"{kind} {name}"] = date
    tests = REPO / "tests" / "game" / mod
    has_tests = tests.is_dir()
    inv = inventory(mod)

    def count(kind: str, name: str) -> str:
        n = seen[kind].get(name, 0)
        who = roots.get(f"{kind} {name}")
        when = first.get(f"{kind} {name}")
        extra = ", ".join(x for x in (f"{len(who)} character(s)" if who else "", f"first {when}" if when else "") if x)
        return f"{n}" + (f" ({extra})" if extra else "")

    unfired = [i for i in inv["events"] if i not in seen["fired"]]
    unchosen = [o for o in inv["options"] if o not in seen["chose"]]
    unrun = [e for e in inv["effects"] if e not in seen["ran"]]
    print(f"In-game tests: {mod} ({'tests in tests/game/' + mod if has_tests else 'no tests; traces only counted'})")
    print(f"events fired: {len(inv['events']) - len(unfired)} of {len(inv['events'])}; "
          f"options chosen: {len(inv['options']) - len(unchosen)} of {len(inv['options'])}")
    for i in inv["events"]:
        print(f"  {i}: {count('fired', i)}")
        for o in (o for o in inv["options"] if o.startswith(i + " ")):
            print(f"    {o[len(i) + 1:]}: {count('chose', o)}")
    if inv["decisions"]:
        print(f"decisions taken: {sum(1 for d in inv['decisions'] if d in seen['took'])} of {len(inv['decisions'])} "
              "(counted, never failed: tests cannot take a decision)")
        for d in inv["decisions"]:
            print(f"  {d}: {count('took', d)}")
    if inv["effects"]:
        print(f"scripted effects run: {len(inv['effects']) - len(unrun)} of {len(inv['effects'])}")
        for e in inv["effects"]:
            print(f"  {e}: {count('ran', e)}")
    for name, n in sorted(seen["pass"].items()):
        print(f"pass: {name}" + (f" (x{n})" if n > 1 else ""))
    for name, n in sorted(seen["fail"].items()):
        details = fail_details.get(name, [])
        more = f" (+{len(details) - 3} more)" if len(details) > 3 else ""
        print(f"FAIL: {name}" + (f" (x{n})" if n > 1 else "") + (": " + " | ".join(details[:3]) + more if details else ""))
    declared = declared_checks(tests) if has_tests else set()
    dynamic = sorted(d for d in declared if "[" in d)
    unreported = sorted(d for d in declared - set(dynamic) if d not in seen["pass"] and d not in seen["fail"])
    for d in unreported:
        print(f"NOT RUN: {d}")
    for d in dynamic:
        print(f"note: check name holds a localisation command, so it is not tracked; put values after ': ': {d}")
    results = run_log_checks(tests / LOG_CHECKS, seen, lines) if (tests / LOG_CHECKS).is_file() else []
    if results:
        print(f"log checks ({LOG_CHECKS}):")
        for ok, check, got in results:
            print(f"  {'pass' if ok else 'FAIL'}: {check} ({got})")
    problems = []
    if seen["fail"]:
        problems.append(f"{len(seen['fail'])} check(s) failed")
    if unreported:
        problems.append(f"{len(unreported)} check(s) never reported")
    if any(not ok for ok, _, _ in results):
        problems.append(f"{sum(1 for ok, _, _ in results if not ok)} log check(s) failed")
    if has_tests and not done:
        problems.append("the tests did not log CK2TEST done")
    if has_tests and unfired:
        problems.append("never fired: " + ", ".join(unfired))
    if has_tests and unchosen:
        problems.append("never chosen: " + ", ".join(unchosen))
    if has_tests and unrun:
        problems.append("never ran: " + ", ".join(unrun))
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
