#!/usr/bin/env python3
"""Create a new mod from mods/_template.

Usage: tools/new_mod.py <folder> --prefix <prefix> [--name "Display Name"]

Writes mods/<folder>/ and mods/<folder>.mod. Files named PREFIX_* are renamed
with the prefix, and {{NAME}}, {{FOLDER}}, {{PREFIX}} are filled in.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODS = ROOT / "mods"
TEMPLATE = MODS / "_template"
ENCODING = "cp1252"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="folder name, lowercase, e.g. allied_fleets")
    ap.add_argument("--prefix", required=True, help="short unique ID prefix, e.g. af")
    ap.add_argument("--name", help="display name in the launcher")
    ap.add_argument("--mods-dir", type=Path, default=MODS, help=argparse.SUPPRESS)
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9_]*", args.folder):
        sys.exit("folder must be lowercase letters, digits and underscores")
    if not re.fullmatch(r"[a-z][a-z0-9]{1,7}", args.prefix):
        sys.exit("prefix must be 2-8 lowercase letters or digits")
    dest = args.mods_dir / args.folder
    if dest.exists():
        sys.exit(f"{dest} already exists")

    values = {
        "{{NAME}}": args.name or args.folder.replace("_", " ").title(),
        "{{FOLDER}}": args.folder,
        "{{PREFIX}}": args.prefix,
    }

    def fill(text: str) -> str:
        for k, v in values.items():
            text = text.replace(k, v)
        return text

    for src in sorted(TEMPLATE.rglob("*")):
        rel = src.relative_to(TEMPLATE)
        if rel.name == "template.mod":
            continue
        out = dest / rel.parent / rel.name.replace("PREFIX", args.prefix)
        if src.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        elif src.suffix in {".txt", ".csv", ".lua", ".gui", ".gfx"}:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(fill(src.read_text(ENCODING)), ENCODING, newline="\n")
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out)

    descriptor = args.mods_dir / f"{args.folder}.mod"
    descriptor.write_text(fill((TEMPLATE / "template.mod").read_text(ENCODING)), ENCODING, newline="\n")
    (dest / "PREFIX").write_text(args.prefix + "\n", "ascii")
    print(f"created {dest.relative_to(args.mods_dir.parent)} and {descriptor.name} (prefix {args.prefix})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
