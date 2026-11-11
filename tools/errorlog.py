#!/usr/bin/env python3
"""Pull the lines that matter from a CK2 error.log.

Usage: tools/errorlog.py <error.log> [mod_folder ...]

Keeps lines that mention a mod folder, its file prefix, or its event
namespace, collapses repeats, and prints a count per line. With no mod
given, every non-template mod in mods/ is used.
"""
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODS = ROOT / "mods"


def needles(folder: str) -> list[str]:
    out = [folder]
    prefix_file = MODS / folder / "PREFIX"
    if prefix_file.exists():
        p = prefix_file.read_text().strip()
        out += [f"{p}_", f"{p}."]
    return out


def main(argv: list[str]) -> int:
    if not argv:
        sys.exit(__doc__)
    log = Path(argv[0])
    folders = argv[1:] or sorted(p.name for p in MODS.iterdir() if p.is_dir() and not p.name.startswith("_"))
    keys = [n for f in folders for n in needles(f)]
    counts: Counter[str] = Counter()
    for line in log.read_bytes().decode("cp1252", "replace").splitlines():
        if any(k in line for k in keys):
            # Drop the leading timestamp so repeats collapse.
            body = line.split("]", 1)[-1].strip() if line.startswith("[") else line.strip()
            counts[body] += 1
    for body, n in counts.most_common():
        print(f"{n:>4}x {body}")
    print(f"{sum(counts.values())} matching line(s), {len(counts)} distinct", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
