#!/usr/bin/env python3
"""Read CK2 saves (Clausewitz text, `CK2txt` header), standard library only (#21 item 6).

Autosaves are plain text when settings.txt has compress_autosaves=no (tools/campaign.sh's games);
a compressed save is a zip holding the text, and is opened too. Text is Windows-1252, read as
latin-1 so every byte survives.

  ck2save.py SAVE info                 date, version, player, and the size of the main sections
  ck2save.py SAVE get PATH             values at PATH: keys joined by '/', '*' matches any key
                                       (e.g. 'character/*/flags', 'date')
  ck2save.py SAVE names PREFIX...      every key or string value that starts with PREFIX_ or
                                       PREFIX. (a mod's flags, modifiers, earmarks, event ids),
                                       with how often it appears
  ck2save.py SAVE check FILE           the checks in FILE (format below); exit 1 when one fails
  ck2save.py SAVE dangling PREFIX DIR...
                                       the save's PREFIX_/PREFIX. names that no file under the DIRs
                                       mentions: state an older version of the mod left that this
                                       version no longer defines; exit 1 when there are any

Check files (tests/game/<mod>/save_checks.txt), one check per line, '#' starts a comment:
  present NAME                 NAME appears in the save as a key or a string value
  absent NAME                  it does not
  count PATH OP N              the number of values at PATH compared with N; OP is one of
                               == != >= <= > <
Each check prints `CK2SAVE pass|fail <line>`.

A parsed block is a list of (key, value) pairs: key is None for a bare value (`{ 1 2 3 }`), value
is a str or another block. Keys repeat (a save has many `character=` style lists), so blocks are
not dicts.
"""
from __future__ import annotations

import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Iterator, List, Optional, Tuple, Union

Value = Union[str, "Block"]
Block = List[Tuple[Optional[str], Value]]

TOKEN = re.compile(rb'"[^"]*"|[{}=]|#[^\n]*|[^\s{}="#]+')
OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
}


def read_text(path: Union[str, Path]) -> bytes:
    """The save's text: the file itself, or the largest member of a zip (a compressed save)."""
    p = Path(path)
    if zipfile.is_zipfile(p):
        with zipfile.ZipFile(p) as z:
            info = max(z.infolist(), key=lambda i: i.file_size)
            return z.read(info)
    return p.read_bytes()


def parse(data: bytes) -> Block:
    """Parse Clausewitz text into a block. Tolerates the `CK2txt` header and stray braces."""
    root: Block = []
    stack = [root]
    toks = [t for t in TOKEN.findall(data) if not t.startswith(b"#")]
    i, n = 0, len(toks)
    while i < n:
        t = toks[i]
        if t == b"}":
            if len(stack) > 1:
                stack.pop()
            i += 1
        elif t == b"{":
            new: Block = []
            stack[-1].append((None, new))
            stack.append(new)
            i += 1
        elif t == b"=":  # a stray '=', e.g. after a value we read as bare
            i += 1
        elif i + 2 < n and toks[i + 1] == b"=":
            key = _text(t)
            if toks[i + 2] == b"{":
                new = []
                stack[-1].append((key, new))
                stack.append(new)
            else:
                stack[-1].append((key, _text(toks[i + 2])))
            i += 3
        else:
            stack[-1].append((None, _text(t)))
            i += 1
    return root


def _text(t: bytes) -> str:
    s = t.decode("latin-1")
    return s[1:-1] if len(s) >= 2 and s[0] == '"' and s[-1] == '"' else s


def load(path: Union[str, Path]) -> Block:
    return parse(read_text(path))


def get(block: Block, path: str) -> List[Value]:
    """Values at PATH ('a/b/c'; '*' matches any key, including a bare value's None)."""
    parts = [p for p in path.split("/") if p]
    found: List[Value] = [block]
    for part in parts:
        nxt: List[Value] = []
        for v in found:
            if isinstance(v, list):
                nxt.extend(val for k, val in v if part == "*" or k == part)
        found = nxt
    return found


def first(block: Block, key: str) -> Optional[Value]:
    for k, v in block:
        if k == key:
            return v
    return None


def walk(block: Block) -> Iterator[Tuple[Optional[str], Value]]:
    """Every (key, value) pair, depth first."""
    stack = [block]
    while stack:
        b = stack.pop()
        for k, v in b:
            yield k, v
            if isinstance(v, list):
                stack.append(v)


def names(block: Block) -> Counter:
    """How often each key and each string value appears."""
    c: Counter = Counter()
    for k, v in walk(block):
        if k is not None:
            c[k] += 1
        if isinstance(v, str):
            c[v] += 1
    return c


def prefixed(block: Block, prefixes: List[str]) -> Counter:
    """The names that start with one of PREFIX_ or PREFIX. (a mod's own names)."""
    starts = tuple(p + s for p in prefixes for s in ("_", "."))
    return Counter({k: v for k, v in names(block).items() if k.startswith(starts)})


def dangling(block: Block, prefix: str, *folders: Union[str, Path]) -> Counter:
    """The save's names with PREFIX that no file under FOLDERS mentions as a whole word."""
    words = set()
    for f in (f for d in folders for f in Path(d).rglob("*")):
        if f.is_file():
            words.update(re.findall(r"[A-Za-z0-9_.@:-]+", f.read_bytes().decode("latin-1")))
    return Counter({k: v for k, v in prefixed(block, [prefix]).items() if k not in words})


def run_checks(block: Block, lines: List[str]) -> Tuple[List[str], int]:
    """Run check lines; return (output lines, number failed)."""
    out: List[str] = []
    failed = 0
    all_names: Optional[Counter] = None
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        words = line.split()
        ok: Optional[bool] = None
        detail = ""
        if words[0] in ("present", "absent") and len(words) == 2:
            if all_names is None:
                all_names = names(block)
            seen = all_names.get(words[1], 0)
            ok = (seen > 0) == (words[0] == "present")
            detail = f"(seen {seen} times)"
        elif words[0] == "count" and len(words) == 4 and words[2] in OPS and words[3].isdigit():
            got = len(get(block, words[1]))
            ok = OPS[words[2]](got, int(words[3]))
            detail = f"(count {got})"
        if ok is None:
            out.append(f"CK2SAVE fail bad check: {line}")
            failed += 1
        else:
            out.append(f"CK2SAVE {'pass' if ok else 'fail'} {line} {detail}")
            failed += 0 if ok else 1
    return out, failed


def _show(v: Value) -> str:
    if isinstance(v, str):
        return v
    return "{ " + " ".join(f"{k}={_show(x) if isinstance(x, str) else '{...}'}" if k else
                           (_show(x) if isinstance(x, str) else "{...}") for k, x in v[:12]) + \
        (" ... }" if len(v) > 12 else " }")


def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    save, cmd, args = argv[0], argv[1], argv[2:]
    block = load(save)
    if cmd == "info":
        for key in ("version", "date", "player_name", "start_date"):
            v = first(block, key)
            print(f"{key}: {v if isinstance(v, str) else '-'}")
        for key in ("character", "dynasties", "provinces", "title", "active_war", "flags"):
            v = first(block, key)
            print(f"{key}: {len(v) if isinstance(v, list) else 0} entries")
        return 0
    if cmd == "get" and len(args) == 1:
        for v in get(block, args[0]):
            print(_show(v))
        return 0
    if cmd == "names" and args:
        for k, v in sorted(prefixed(block, args).items()):
            print(f"{v:6d} {k}")
        return 0
    if cmd == "dangling" and len(args) >= 2:
        left = dangling(block, args[0], *args[1:])
        for k, v in sorted(left.items()):
            print(f"{v:6d} {k}")
        return 1 if left else 0
    if cmd == "check" and len(args) == 1:
        out, failed = run_checks(block, Path(args[0]).read_text(encoding="latin-1").splitlines())
        print("\n".join(out))
        return 1 if failed else 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
