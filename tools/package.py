#!/usr/bin/env python3
"""Build dist/<mod>.zip containing <mod>.mod and <mod>/, ready to unzip into the CK2 mod folder.

Usage: tools/package.py <mod_folder>
"""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODS = ROOT / "mods"
SKIP = {"PREFIX", ".gitkeep"}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        sys.exit(__doc__)
    folder = argv[0]
    mod, descriptor = MODS / folder, MODS / f"{folder}.mod"
    if not mod.is_dir() or not descriptor.exists():
        sys.exit(f"need mods/{folder}/ and mods/{folder}.mod")
    out = ROOT / "dist" / f"{folder}.zip"
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(descriptor, descriptor.name)
        for path in sorted(mod.rglob("*")):
            if path.is_file() and path.name not in SKIP:
                z.write(path, Path(folder) / path.relative_to(mod))
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
