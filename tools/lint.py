#!/usr/bin/env python3
"""Static checks for CK2 mods in mods/.

Usage: tools/lint.py [--cwtools] [mod_folder ...]   (default: every mod except _template)

--cwtools also runs tools/cwtools_check.py (CWTools rules: unknown effects,
triggers, scopes, traits). Its findings are warnings and never fail lint.

Errors (exit 1):
  - descriptor mods/<mod>.mod missing, or its path does not point at mod/<mod>
  - script file not decodable as Windows-1252
  - unbalanced braces in a script file
  - duplicate event id, or duplicate localisation key, inside the mod
  - localisation line without ';' separators
Warnings:
  - non-ASCII characters (check they show correctly in game)
  - UTF-8 byte order mark
  - event id not using the mod's prefix (from mods/<mod>/PREFIX)
  - desc/name/title key not found in the mod's or vanilla localisation

Vanilla localisation is read from vanilla/localisation when present.
This is a heuristic checker, not a full CK2 parser; the game's error.log
is still the final word.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODS = ROOT / "mods"
VANILLA = ROOT / "vanilla"
SCRIPT_SUFFIXES = {".txt", ".gui", ".gfx", ".lua"}
ENCODING = "cp1252"

EVENT_ID = re.compile(r"^\s*id\s*=\s*([A-Za-z0-9_]+\.[0-9]+)\b", re.M)
LOC_REF = re.compile(r"\b(?:desc|name|title)\s*=\s*([A-Za-z][A-Za-z0-9_]*)\s*(?:#|$)", re.M)


class Report:
    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0

    def error(self, path: Path, msg: str) -> None:
        self.errors += 1
        print(f"ERROR {rel(path)}: {msg}")

    def warn(self, path: Path, msg: str) -> None:
        self.warnings += 1
        print(f"warn  {rel(path)}: {msg}")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def read(path: Path, rep: Report) -> str | None:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        rep.warn(path, "starts with a UTF-8 byte order mark")
        data = data[3:]
    try:
        text = data.decode(ENCODING)
    except UnicodeDecodeError as e:
        rep.error(path, f"not valid Windows-1252 at byte {e.start}")
        return None
    if any(ord(c) > 127 for c in text):
        line = next(i for i, l in enumerate(text.splitlines(), 1) if any(ord(c) > 127 for c in l))
        rep.warn(path, f"non-ASCII characters (first on line {line}); check they show correctly in game")
    return text


def strip_comments(text: str) -> str:
    """Remove # comments, ignoring # inside double-quoted strings."""
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


def check_braces(path: Path, text: str, rep: Report) -> None:
    depth = 0
    in_str = False
    for n, line in enumerate(text.splitlines(), 1):
        for c in line:
            if c == '"':
                in_str = not in_str
            elif not in_str and c == "{":
                depth += 1
            elif not in_str and c == "}":
                depth -= 1
                if depth < 0:
                    rep.error(path, f"line {n}: '}}' with no matching '{{'")
                    return
        in_str = False
    if depth:
        rep.error(path, f"{depth} unclosed '{{' at end of file")


def load_loc(files: list[Path], rep: Report | None, keys: dict[str, Path]) -> None:
    for path in files:
        text = read(path, rep) if rep else path.read_bytes().decode(ENCODING, "replace")
        if text is None:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if not line.strip() or line.startswith("#"):
                continue
            if ";" not in line:
                if rep:
                    rep.error(path, f"line {n}: no ';' separator")
                continue
            key = line.split(";", 1)[0].strip()
            if rep and key in keys and keys[key].parent == path.parent:
                rep.error(path, f"line {n}: duplicate key {key} (also in {rel(keys[key])})")
            keys.setdefault(key, path)


def lint_mod(folder: str, vanilla_keys: dict[str, Path], rep: Report) -> None:
    mod = MODS / folder
    if not mod.is_dir():
        rep.error(mod, "no such mod folder")
        return
    descriptor = MODS / f"{folder}.mod"
    if not descriptor.exists():
        rep.error(descriptor, "descriptor missing")
    else:
        text = read(descriptor, rep) or ""
        m = re.search(r'^\s*path\s*=\s*"([^"]+)"', text, re.M)
        if not m or m.group(1) != f"mod/{folder}":
            rep.error(descriptor, f'path must be "mod/{folder}"')
        if not re.search(r'^\s*name\s*=\s*"[^"]+"', text, re.M):
            rep.error(descriptor, "name missing")

    prefix_file = mod / "PREFIX"
    prefix = prefix_file.read_text().strip() if prefix_file.exists() else None

    mod_keys: dict[str, Path] = {}
    load_loc(sorted((mod / "localisation").glob("*.csv")), rep, mod_keys)

    event_ids: dict[str, Path] = {}
    refs: list[tuple[Path, str]] = []
    for path in sorted(mod.rglob("*")):
        if path.suffix not in SCRIPT_SUFFIXES or not path.is_file():
            continue
        text = read(path, rep)
        if text is None:
            continue
        code = strip_comments(text)
        check_braces(path, code, rep)
        if path.suffix != ".txt":
            continue
        if "events" in path.relative_to(mod).parts:
            for eid in EVENT_ID.findall(code):
                if eid in event_ids:
                    rep.error(path, f"duplicate event id {eid} (also in {rel(event_ids[eid])})")
                event_ids.setdefault(eid, path)
                if prefix and not eid.startswith(prefix + "."):
                    rep.warn(path, f"event id {eid} does not use prefix {prefix}")
        refs += [(path, k) for k in LOC_REF.findall(code)]

    for path, key in refs:
        if key in mod_keys or key in vanilla_keys or key in ("yes", "no"):
            continue
        if key.isupper() or "_" in key:
            where = "mod or vanilla" if vanilla_keys else "mod (vanilla/ not present)"
            rep.warn(path, f"localisation key {key} not found in {where}")


def main(argv: list[str]) -> int:
    use_cwtools = "--cwtools" in argv
    argv = [a for a in argv if a != "--cwtools"]
    folders = argv or sorted(p.name for p in MODS.iterdir() if p.is_dir() and not p.name.startswith("_"))
    vanilla_keys: dict[str, Path] = {}
    if (VANILLA / "localisation").is_dir():
        load_loc(sorted((VANILLA / "localisation").glob("*.csv")), None, vanilla_keys)
    rep = Report()
    for folder in folders:
        lint_mod(folder, vanilla_keys, rep)
    print(f"{len(folders)} mod(s) checked: {rep.errors} error(s), {rep.warnings} warning(s)")
    if use_cwtools and folders:
        import cwtools_check
        cwtools_check.main(folders)
    return 1 if rep.errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
