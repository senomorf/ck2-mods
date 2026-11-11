import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import steam_fetch_vanilla as sfv  # noqa: E402

GRID = [[(x * 7 + y * 3) % 5 < 2 for x in range(25)] for y in range(25)]
ASCII = ["  " * 2 + "".join("██" if c else "  " for c in row) + "  " * 2 for row in GRID]

FAKE_DD = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import os, sys
    from pathlib import Path
    args = sys.argv[1:]
    out = Path(args[args.index("-dir") + 1])
    print("Logging in with QR code...")
    print("Use the Steam Mobile App to sign in with this QR code:")
    print("")
    for line in {ascii!r}:
        print(line)
    print("")
    marker = Path(os.environ["HOME"]) / ".local" / "share" / "IsolatedStorage" / "account.config"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("token")
    print("Downloading depot 203771 - manifest 1234567890")
    print(" 50.00% events/test.txt")
    (out / "events").mkdir(parents=True)
    (out / "events" / "test.txt").write_text("namespace = test")
    (out / "localisation").mkdir()
    (out / "localisation" / "x.csv").write_text("A;B;x")
    (out / ".DepotDownloader").mkdir()
    (out / ".DepotDownloader" / "depot.config").write_text("x")
    print("Total downloaded: 2 files")
    """
).format(ascii=ASCII)


class SteamFetchTest(unittest.TestCase):
    def test_parse_ascii_qr(self) -> None:
        grid = sfv.parse_ascii_qr(ASCII)
        self.assertIsNotNone(grid)
        # Quiet zone of 2 modules each side, then the original grid.
        self.assertEqual([row[2:-2] for row in grid], GRID)

    def test_write_png(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "qr.png"
            sfv.write_png(GRID, p, scale=4, border=4)
            data = p.read_bytes()
            self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
            width = int.from_bytes(data[16:20], "big")
            self.assertEqual(width, (25 + 8) * 4)

    def _run(self, *extra: str, cache: Path, dd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / "steam_fetch_vanilla.py"), "--cache", str(cache),
             "--depotdownloader", str(dd), *extra],
            capture_output=True, text=True,
        )

    def test_end_to_end_with_fake_depotdownloader(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            dd = d / "DepotDownloader"
            dd.write_text(FAKE_DD)
            dd.chmod(0o755)
            cache = d / "ck2-cache"

            r = self._run("--qr", cache=cache, dd=dd)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("QR code ready", r.stdout)
            self.assertNotIn("50.00%", r.stdout)
            self.assertFalse((cache / "steam-login-qr.png").exists(), "QR png removed after run")
            self.assertFalse((cache / "steam-home").exists(), "token not kept without --keep-login")

            out = d / "ck2-vanilla" / "ck2-game-files.zip"
            names = zipfile.ZipFile(out).namelist()
            self.assertEqual(sorted(names), ["events/test.txt", "localisation/x.csv"])
            meta = json.loads(out.with_suffix(".json").read_text())
            self.assertEqual(meta["files"], 2)
            self.assertEqual(meta["app"], "203770")
            self.assertTrue(any("manifest 1234567890" in m for m in meta["manifests"]))

            r = self._run("--qr", "--keep-login", cache=cache, dd=dd)
            self.assertEqual(r.returncode, 0, r.stderr)
            token = cache / "steam-home" / ".local" / "share" / "IsolatedStorage" / "account.config"
            self.assertTrue(token.exists())
            self.assertEqual(os.stat(cache / "steam-home").st_mode & 0o777, 0o700)

    def test_requires_login_mode(self) -> None:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "steam_fetch_vanilla.py")], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--qr", r.stderr)


if __name__ == "__main__":
    unittest.main()
