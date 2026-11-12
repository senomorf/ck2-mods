#!/usr/bin/env python3
"""Download CK2's script files from Steam and cache them as one zip.

Uses DepotDownloader (installed by tools/cloud_setup.sh) with Steam's QR
login, so no password is ever typed or stored. Only the folders agents need
are downloaded (see FILELIST), not the multi-GB graphics and audio.

Usage:
  tools/steam_fetch_vanilla.py --qr            first time: shows a QR code to scan
  tools/steam_fetch_vanilla.py --qr --keep-login   also keep the Steam session token
  tools/steam_fetch_vanilla.py --username NAME     reuse a kept session (no QR; keeps it)

While waiting for the scan, the QR code is written as a PNG to
<cache>/steam-login-qr.png (re-written whenever Steam refreshes it). The agent
posts that image to the user, who scans it in the Steam mobile app
(Steam Guard > Scan a QR code).

Output (the cache, on the Claude project's shared files by default):
  <cache>/../ck2-vanilla/ck2-game-files.zip   unpacked into vanilla/ by the session hook
  <cache>/../ck2-vanilla/ck2-game-files.json  what was downloaded, when, depot manifests
  <cache>/steam-home/                         Steam session token, only with --keep-login

The token in steam-home lets anyone with access to the project's files
download with your account, so it is deleted after each run unless
--keep-login is given. CK2 no longer receives patches, so one download
normally lasts; a later run is only needed if the cache is lost.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_ID = "203770"  # Crusader Kings II
DEFAULT_CACHE = Path("/mnt/project-files/ck2-cache")
FILELIST = [
    r"regex:^(common|decisions|events|history|localisation|interface)/",
    r"regex:^map/[^/]+\.(txt|csv|map)$",
    r"regex:^[^/]+\.(txt|json|lua)$",
]
QR_CHARS = set("█ ")


# ---------- QR code: DepotDownloader prints it as text; we render a PNG ----------

def parse_ascii_qr(lines: list[str]) -> list[list[bool]] | None:
    """Turn DepotDownloader's block-character QR code into a module grid."""
    rows = [l.rstrip("\n") for l in lines if l.strip() and set(l.rstrip("\n")) <= QR_CHARS]
    if len(rows) < 21:
        return None
    width = max(len(r) for r in rows)
    rows = [r.ljust(width) for r in rows]
    runs = [len(m.group(0)) for r in rows for m in re.finditer(r"█+| +", r)]
    unit = min(runs) if runs else 1
    grid = [[r[i] == "█" for i in range(0, width, unit)] for r in rows]
    # Drop DepotDownloader's own padding; write_png adds an even quiet zone.
    cols = [x for x in range(len(grid[0])) if any(row[x] for row in grid)]
    grid = [row[cols[0]:cols[-1] + 1] for row in grid if any(row)]
    return grid


def write_png(grid: list[list[bool]], path: Path, scale: int = 8, border: int = 4) -> None:
    """Write a black-on-white PNG of the grid, standard library only."""
    h, w = len(grid), len(grid[0])
    W, H = (w + 2 * border) * scale, (h + 2 * border) * scale
    raw = bytearray()
    for y in range(H):
        gy = y // scale - border
        raw.append(0)
        for x in range(W):
            gx = x // scale - border
            dark = 0 <= gy < h and 0 <= gx < w and grid[gy][gx]
            raw.append(0 if dark else 255)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 0, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(png)
    tmp.replace(path)


# ---------- download, then pack into the cache ----------

def run_depotdownloader(cmd: list[str], env: dict, qr_png: Path, log_path: Path) -> tuple[int, list[str]]:
    manifests: list[str] = []
    block: list[str] = []
    with open(log_path, "w") as log, subprocess.Popen(
        cmd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace",
    ) as proc:
        assert proc.stdout
        for line in proc.stdout:
            log.write(line)
            log.flush()
            if set(line.rstrip("\n")) <= QR_CHARS and line.strip():
                block.append(line)
                continue
            if block:
                grid = parse_ascii_qr(block)
                block = []
                if grid:
                    write_png(grid, qr_png)
                    print(f"QR code ready: {qr_png} (scan in the Steam mobile app)", flush=True)
                continue
            if re.search(r"manifest \d+", line, re.I):
                manifests.append(line.strip())
            if not re.match(r"^\s*\d+(\.\d+)?%", line):  # skip per-file progress
                print(line, end="", flush=True)
    return proc.returncode, manifests


def pack(download_dir: Path, out_zip: Path, meta: dict) -> dict:
    files = sorted(p for p in download_dir.rglob("*") if p.is_file() and ".DepotDownloader" not in p.parts)
    if not any(p.relative_to(download_dir).parts[0] == "events" for p in files):
        sys.exit(f"download looks incomplete: no events/ folder in {download_dir}")
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_zip.with_suffix(".zip.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            z.write(p, p.relative_to(download_dir))
    digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
    tmp.replace(out_zip)
    meta.update(files=len(files), bytes=sum(p.stat().st_size for p in files), zip_sha256=digest)
    out_zip.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--qr", action="store_true", help="log in by scanning a QR code")
    ap.add_argument("--username", help="Steam account name, to reuse a kept session")
    ap.add_argument("--keep-login", action="store_true", help="keep the Steam session token in the cache")
    ap.add_argument("--cache", type=Path, default=Path(os.environ.get("CK2_CACHE_DIR", DEFAULT_CACHE)))
    ap.add_argument("--depotdownloader", default=os.environ.get("DEPOTDOWNLOADER", "DepotDownloader"))
    ap.add_argument("--os", default="windows", help="depot platform; script files match across platforms")
    args = ap.parse_args(argv)
    if not args.qr and not args.username:
        ap.error("give --qr (first time) or --username (with a kept session)")
    if shutil.which(args.depotdownloader) is None and not Path(args.depotdownloader).is_file():
        sys.exit("DepotDownloader not found; run tools/cloud_setup.sh (needs a network that allows github.com and Steam)")

    cache: Path = args.cache
    cache.mkdir(parents=True, exist_ok=True)
    steam_home = cache / "steam-home"
    qr_png = cache / "steam-login-qr.png"
    out_zip = cache.parent / "ck2-vanilla" / "ck2-game-files.zip"

    with tempfile.TemporaryDirectory() as work_s:
        work = Path(work_s)
        home = work / "home"
        if steam_home.is_dir():
            shutil.copytree(steam_home, home)
        home.mkdir(exist_ok=True)
        download = work / "game"
        filelist = work / "filelist.txt"
        filelist.write_text("\n".join(FILELIST) + "\n")

        cmd = [args.depotdownloader, "-app", APP_ID, "-os", args.os, "-dir", str(download), "-filelist", str(filelist)]
        cmd += ["-qr"] if args.qr else ["-username", args.username]
        cmd += ["-remember-password"]
        # DepotDownloader keeps its session in the user's isolated storage under HOME.
        env = dict(os.environ, HOME=str(home), XDG_DATA_HOME=str(home / ".local" / "share"))

        started = datetime.datetime.now(datetime.timezone.utc)
        code, manifests = run_depotdownloader(cmd, env, qr_png, work / "depotdownloader.log")
        qr_png.unlink(missing_ok=True)
        shutil.copy(work / "depotdownloader.log", cache / "last-run.log")

        # A run that reuses a kept session keeps it; a QR run keeps it only if asked.
        if args.keep_login or args.username:
            if steam_home.exists():
                shutil.rmtree(steam_home)
            shutil.copytree(home, steam_home)
            os.chmod(steam_home, 0o700)
        elif steam_home.exists():
            shutil.rmtree(steam_home)

        if code != 0:
            print(f"DepotDownloader exited {code}; see {cache / 'last-run.log'}", file=sys.stderr)
            return code
        meta = pack(download, out_zip, {
            "app": APP_ID,
            "os": args.os,
            "downloaded_at": started.isoformat(timespec="seconds"),
            "filelist": FILELIST,
            "manifests": manifests,
        })
    print(f"cached {meta['files']} files ({meta['bytes'] // 1_000_000} MB) in {out_zip}")
    print("unpack now with: tools/fetch_vanilla.sh " + str(out_zip))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
