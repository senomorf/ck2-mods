#!/usr/bin/env python3
"""Validate mods with the CWTools CLI against the CK2 rules in .cwtools/.

Usage: tools/cwtools_check.py [--strict] [mod_folder ...]   (default: every mod except _template)

CWTools checks what tools/lint.py cannot: unknown effects and triggers, wrong
scopes, undefined traits/modifiers/flags. Its CK2 rules date from 2019 and it
reports ~28,000 errors on vanilla 3.3.3 itself, so its findings are warnings:
check each one against vanilla/ before acting on it. Patterns known to be
false positives are listed, with the vanilla file that disproves them, in
tools/cwtools_ignore.txt.

Needs `cwtools` on PATH (tools/cloud_setup.sh), .cwtools/ (session hook) and
vanilla/ (game files). If any is missing it says so and exits 0.

The first run builds a cache of vanilla (~20 s, ~250 MB) in .cache/cwtools/;
later runs take ~30 s. Exit 1 only with --strict and findings left after the
ignore list.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODS = ROOT / "mods"
VANILLA = ROOT / "vanilla"
RULES = ROOT / ".cwtools"
CACHE_DIR = ROOT / ".cache" / "cwtools"
IGNORE = ROOT / "tools" / "cwtools_ignore.txt"


def load_ignores() -> list[re.Pattern]:
    if not IGNORE.exists():
        return []
    lines = IGNORE.read_text().splitlines()
    return [re.compile(l) for l in lines if l.strip() and not l.startswith("#")]


def vanilla_stamp() -> str:
    stamp = VANILLA / ".source.sha256"
    if stamp.exists():
        return stamp.read_text().strip()
    files = sorted(VANILLA.rglob("*"))
    return f"{len(files)}-{max((p.stat().st_mtime for p in files), default=0)}"


def ensure_cache(exe: str) -> Path | None:
    cache = CACHE_DIR / "vanilla.cwb"
    stamp_file = CACHE_DIR / "vanilla.stamp"
    want = vanilla_stamp()
    if cache.exists() and stamp_file.exists() and stamp_file.read_text() == want:
        return cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    print("cwtools: building vanilla cache (once per game-files version)...", flush=True)
    r = subprocess.run(
        [exe, "--directory", str(VANILLA), "--game", "ck2", "--scope", "vanilla", "--rulespath", str(RULES),
         "serialize", "--outputcachefile", str(cache), "full"],
        cwd=CACHE_DIR, capture_output=True, text=True,
    )
    if r.returncode != 0 or not cache.exists():
        print(f"cwtools: could not build vanilla cache:\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
        return None
    stamp_file.write_text(want)
    return cache


def run(folders: list[str], exe: str, cache: Path) -> list[tuple[str, int, str, str]]:
    """Return (repo-relative path, line, category, message) for each finding."""
    with tempfile.TemporaryDirectory() as tmp_s:
        tmp = Path(tmp_s)
        # CWTools finds mods as <directory>/mod/<folder> plus <folder>.mod.
        # Copies, not symlinks, since symlinked folders are not reliably read.
        for f in folders:
            shutil.copytree(MODS / f, tmp / "mod" / f)
            if (MODS / f"{f}.mod").exists():
                shutil.copy(MODS / f"{f}.mod", tmp / "mod" / f"{f}.mod")
        out = tmp / "report.json"
        r = subprocess.run(
            [exe, "--directory", str(tmp), "--game", "ck2", "--scope", "mods", "--rulespath", str(RULES),
             "--cachefile", str(cache), "--cachetype", "full",
             "validate", "--reporttype", "json", "--outputfile", str(out), "errors"],
            cwd=tmp, capture_output=True, text=True,
        )
        if not out.exists():
            raise RuntimeError(f"cwtools produced no report (exit {r.returncode}):\n{r.stdout[-2000:]}{r.stderr[-2000:]}")
        report = json.loads(out.read_text())
        findings = []
        prefix = str((tmp / "mod").resolve()) + "/"
        for entry in report.get("files", []):
            path = str(Path(entry["file"]).resolve())
            path = "mods/" + path[len(prefix):] if path.startswith(prefix) else path
            for e in entry.get("errors", []):
                msg = " ".join(e["message"].split())
                findings.append((path, e["position"]["startLine"], e["category"], msg))
        return sorted(set(findings))


def main(argv: list[str]) -> int:
    strict = "--strict" in argv
    folders = [a for a in argv if not a.startswith("--")]
    folders = folders or sorted(p.name for p in MODS.iterdir() if p.is_dir() and not p.name.startswith("_"))
    exe = shutil.which("cwtools")
    missing = [n for n, ok in [("cwtools CLI (tools/cloud_setup.sh)", exe),
                               (".cwtools/ rules (session hook)", (RULES / "effects.cwt").exists()),
                               ("vanilla/ game files (game-files skill)", VANILLA.is_dir())] if not ok]
    if missing:
        print("cwtools: skipped, missing " + ", ".join(missing))
        return 0
    if not folders:
        print("cwtools: no mods to check")
        return 0
    cache = ensure_cache(exe)
    if cache is None:
        return 1 if strict else 0
    ignores = load_ignores()
    findings = run(folders, exe, cache)
    shown = [f for f in findings if not any(p.search(f[3]) for p in ignores)]
    for path, line, cat, msg in shown:
        print(f"cwtools {path}:{line}: {cat} {msg}")
    print(f"cwtools: {len(folders)} mod(s), {len(shown)} finding(s), {len(findings) - len(shown)} ignored as known false positives")
    return 1 if strict and shown else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
