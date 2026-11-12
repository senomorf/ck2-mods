#!/usr/bin/env python3
"""Cross-reference checks for CK2 mods: things the game only reports at run
time, or never, because each file is fine on its own.

Usage: tools/xref.py [mod_folder ...]   (also run by tools/lint.py)

Errors (exit 1):
  - an event fired with the mod's prefix (character_event = { id = <prefix>.N })
    that the mod does not define
Warnings:
  - an event fired that neither the mod nor vanilla/ defines
  - an is_triggered_only event of the mod that nothing in the mod fires
    (it may still be fired from the console or another mod)
  - a decision without <name> or <name>_desc localisation
  - a character/province/title/global flag that is checked or cleared but never set,
    or set but never checked or cleared, in the mod and vanilla
  - event_target:X used but never saved with save_event_target_as / save_global_event_target_as
  - has_earmarked_regiments = X where no spawn_unit/spawn_fleet uses earmark = X

Vanilla definitions are read from vanilla/ when present; without it, checks
that need vanilla are limited to names using the mod's prefix.
"""
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODS = ROOT / "mods"
VANILLA = ROOT / "vanilla"
ENCODING = "cp1252"

EVENT_TYPES = {
    "character_event", "diploresponse_event", "letter_event", "long_character_event", "narrative_event",
    "province_event", "repeat_event", "society_quest_event", "unit_event",
}
DECISION_BLOCKS = {
    "decisions", "targeted_decisions", "title_decisions", "settlement_decisions",
    "society_decisions", "plot_decisions",
}
FLAG_KINDS = ("character", "province", "title", "global", "dynasty", "religion")
TOKEN = re.compile(r'"[^"\n]*"|[{}]|[<>]=?|==?|[^\s{}=<>"]+')


@dataclass
class Node:
    key: str
    value: "str | list[Node]"
    line: int


def strip_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        in_str = False
        for i, c in enumerate(line):
            if c == '"':
                in_str = not in_str
            elif c == "#" and not in_str:
                line = line[:i]
                break
        out.append(line)
    return "\n".join(out)


def parse(text: str) -> list[Node]:
    """Parse Clausewitz script into nodes. Bare values become Node(value, '', line).
    Tolerant: unbalanced braces are lint.py's job, not this one's."""
    text = strip_comments(text)
    tokens: list[tuple[str, int]] = []
    for n, line in enumerate(text.splitlines(), 1):
        tokens += [(t, n) for t in TOKEN.findall(line)]
    pos = 0

    def block() -> list[Node]:
        nonlocal pos
        nodes: list[Node] = []
        while pos < len(tokens):
            tok, line = tokens[pos]
            if tok == "}":
                pos += 1
                return nodes
            if tok == "{":  # anonymous block
                pos += 1
                nodes.append(Node("", block(), line))
                continue
            pos += 1
            if pos < len(tokens) and tokens[pos][0] in ("=", "==", "<", ">", "<=", ">="):
                pos += 1
                if pos < len(tokens) and tokens[pos][0] == "{":
                    pos += 1
                    nodes.append(Node(tok, block(), line))
                elif pos < len(tokens):
                    nodes.append(Node(tok, tokens[pos][0].strip('"'), line))
                    pos += 1
            else:
                nodes.append(Node(tok.strip('"'), "", line))
        return nodes

    result: list[Node] = []
    while pos < len(tokens):
        result += block()
    return result


def walk(nodes: list[Node]):
    for n in nodes:
        yield n
        if isinstance(n.value, list):
            yield from walk(n.value)


def child(n: Node, key: str) -> str | None:
    if isinstance(n.value, list):
        for c in n.value:
            if c.key == key and isinstance(c.value, str):
                return c.value
    return None


@dataclass
class Index:
    """Names defined (or used) somewhere, with one location for messages."""
    events: dict[str, tuple[Path, int, bool]] = field(default_factory=dict)  # id -> (file, line, triggered_only)
    fired: dict[str, list[tuple[Path, int]]] = field(default_factory=dict)
    flags_set: dict[str, tuple[Path, int]] = field(default_factory=dict)
    flags_used: dict[str, tuple[Path, int]] = field(default_factory=dict)
    targets_saved: set[str] = field(default_factory=set)
    targets_used: dict[str, tuple[Path, int]] = field(default_factory=dict)
    earmarks_made: set[str] = field(default_factory=set)
    earmarks_checked: dict[str, tuple[Path, int]] = field(default_factory=dict)
    decisions: dict[str, tuple[Path, int]] = field(default_factory=dict)


def index_file(path: Path, idx: Index, text: str | None = None) -> None:
    if text is None:
        text = path.read_bytes().decode(ENCODING, "replace")
    nodes = parse(text)
    in_events = "events" in path.parts
    for n in nodes:
        if n.key in EVENT_TYPES and in_events and isinstance(n.value, list):
            eid = child(n, "id")
            if eid:
                idx.events.setdefault(eid, (path, n.line, child(n, "is_triggered_only") == "yes"))
        if n.key in DECISION_BLOCKS and isinstance(n.value, list) and "decisions" in path.parts:
            for d in n.value:
                if isinstance(d.value, list):
                    idx.decisions.setdefault(d.key, (path, d.line))
    top = {id(n) for n in nodes}
    for n in walk(nodes):
        k, v = n.key, n.value
        if k in EVENT_TYPES and id(n) not in top:
            eid = child(n, "id") if isinstance(v, list) else None
            if eid:
                idx.fired.setdefault(eid, []).append((path, n.line))
        elif k == "events" and isinstance(v, list) and "on_actions" in path.parts:
            for e in v:
                if e.value == "":
                    idx.fired.setdefault(e.key, []).append((path, e.line))
        if k == "save_persistent_event_target" and isinstance(v, list):
            name = child(n, "name")
            if name:
                idx.targets_saved.add(name)
        if not isinstance(v, str):
            continue
        for kind in FLAG_KINDS:
            if k == f"set_{kind}_flag":
                idx.flags_set.setdefault(f"{kind}:{v}", (path, n.line))
            elif k in (f"has_{kind}_flag", f"clr_{kind}_flag", f"had_{kind}_flag"):
                idx.flags_used.setdefault(f"{kind}:{v}", (path, n.line))
        if k in ("save_event_target_as", "save_global_event_target_as", "save_persistent_event_target"):
            idx.targets_saved.add(v)
        elif k == "earmark":
            idx.earmarks_made.add(v)
        elif k in ("has_earmarked_regiments", "has_earmarked_regiments_not_raiding"):
            idx.earmarks_checked.setdefault(v, (path, n.line))
    for m in re.finditer(r"event_target:([A-Za-z0-9_]+)", strip_comments(text)):
        idx.targets_used.setdefault(m.group(1), (path, text.count("\n", 0, m.start()) + 1))


_vanilla_cache: Index | None = None


def vanilla_index() -> Index | None:
    global _vanilla_cache
    if _vanilla_cache is None and VANILLA.is_dir():
        idx = Index()
        for sub in ("events", "decisions", "common"):
            for p in sorted((VANILLA / sub).rglob("*.txt")):
                index_file(p, idx)
        _vanilla_cache = idx
    return _vanilla_cache


def loc_keys(folder: Path) -> set[str]:
    keys = set()
    for p in sorted(folder.glob("*.csv")):
        for line in p.read_bytes().decode(ENCODING, "replace").splitlines():
            if ";" in line and not line.startswith("#"):
                keys.add(line.split(";", 1)[0].strip())
    return keys


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def check_mod(folder: str, report) -> None:
    """report(kind, path, line, message) with kind 'error' or 'warn'."""
    mod = MODS / folder
    prefix_file = mod / "PREFIX"
    prefix = prefix_file.read_text().strip() if prefix_file.exists() else None
    idx = Index()
    for p in sorted(mod.rglob("*.txt")):
        if p.is_file():
            index_file(p, idx)
    van = vanilla_index()

    def ours(name: str) -> bool:
        return bool(prefix) and (name == prefix or name.startswith(prefix + ".") or name.startswith(prefix + "_"))

    for eid, places in sorted(idx.fired.items()):
        if eid in idx.events or (van and eid in van.events):
            continue
        path, line = places[0]
        if ours(eid):
            report("error", path, line, f"fires event {eid}, which the mod does not define")
        elif van:
            report("warn", path, line, f"fires event {eid}, not defined in the mod or vanilla")

    for eid, (path, line, triggered) in sorted(idx.events.items()):
        if triggered and eid not in idx.fired:
            report("warn", path, line, f"event {eid} is_triggered_only but nothing in the mod fires it")

    keys = loc_keys(mod / "localisation")
    van_keys = loc_keys(VANILLA / "localisation") if VANILLA.is_dir() else set()
    for name, (path, line) in sorted(idx.decisions.items()):
        for key in (name, f"{name}_desc"):
            if key not in keys and key not in van_keys:
                report("warn", path, line, f"decision {name} has no localisation key {key}")

    for flag, (path, line) in sorted(idx.flags_used.items()):
        if flag not in idx.flags_set and not (van and flag in van.flags_set):
            if ours(flag.split(":", 1)[1]) or van:
                report("warn", path, line, f"{flag.replace(':', ' flag ')} is checked or cleared but never set")
    for flag, (path, line) in sorted(idx.flags_set.items()):
        if flag not in idx.flags_used and not (van and flag in van.flags_used):
            report("warn", path, line, f"{flag.replace(':', ' flag ')} is set but never checked or cleared")

    for t, (path, line) in sorted(idx.targets_used.items()):
        if t not in idx.targets_saved and not (van and t in van.targets_saved):
            if ours(t) or van:
                report("warn", path, line, f"event_target:{t} is never saved (save_event_target_as)")

    for e, (path, line) in sorted(idx.earmarks_checked.items()):
        if e not in idx.earmarks_made and not (van and e in van.earmarks_made):
            if ours(e) or van:
                report("warn", path, line, f"earmark {e} is checked but no spawn_unit/spawn_fleet creates it")


def main(argv: list[str]) -> int:
    folders = argv or sorted(p.name for p in MODS.iterdir() if p.is_dir() and not p.name.startswith("_"))
    counts = {"error": 0, "warn": 0}

    def report(kind: str, path: Path, line: int, msg: str) -> None:
        counts[kind] += 1
        print(f"{'ERROR' if kind == 'error' else 'warn '} {rel(path)}:{line}: {msg}")

    for f in folders:
        check_mod(f, report)
    print(f"xref: {len(folders)} mod(s): {counts['error']} error(s), {counts['warn']} warning(s)")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
