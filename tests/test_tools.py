import contextlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import lint  # noqa: E402


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=ROOT, capture_output=True, text=True)


class ToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = "zz_selftest"
        self.mod = ROOT / "mods" / self.folder
        self.descriptor = ROOT / "mods" / f"{self.folder}.mod"
        self.addCleanup(shutil.rmtree, self.mod, ignore_errors=True)
        self.addCleanup(self.descriptor.unlink, missing_ok=True)
        r = run("tools/new_mod.py", self.folder, "--prefix", "zzt", "--name", "Self Test")
        self.assertEqual(r.returncode, 0, r.stderr)

    def lint(self) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = lint.main([self.folder])
        return code, out.getvalue()

    def test_new_mod_scaffold(self) -> None:
        self.assertTrue((self.mod / "events" / "zzt_events.txt").exists())
        self.assertIn('path = "mod/zz_selftest"', self.descriptor.read_text())
        self.assertIn("namespace = zzt", (self.mod / "events" / "zzt_events.txt").read_text())

    def test_template_lints_clean(self) -> None:
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        self.assertIn("0 error(s)", out)

    def test_unbalanced_braces(self) -> None:
        (self.mod / "events" / "zzt_bad.txt").write_text("namespace = zzt\ncharacter_event = {\n\tid = zzt.2\n")
        code, out = self.lint()
        self.assertEqual(code, 1)
        self.assertIn("unclosed", out)

    def test_brace_in_comment_and_string_ignored(self) -> None:
        (self.mod / "events" / "zzt_ok.txt").write_text('# { not code\nx = "a { b"\n')
        code, out = self.lint()
        self.assertEqual(code, 0, out)

    def test_duplicate_event_id(self) -> None:
        (self.mod / "events" / "zzt_dup.txt").write_text("character_event = {\n\tid = zzt.1\n}\n")
        code, out = self.lint()
        self.assertEqual(code, 1)
        self.assertIn("duplicate event id zzt.1", out)

    def test_wrong_prefix_warns(self) -> None:
        (self.mod / "events" / "zzt_other.txt").write_text("character_event = {\n\tid = abc.1\n}\n")
        _, out = self.lint()
        self.assertIn("does not use prefix zzt", out)

    def test_missing_loc_key_warns(self) -> None:
        (self.mod / "events" / "zzt_loc.txt").write_text("character_event = {\n\tid = zzt.3\n\tdesc = EVTDESC_zzt_3\n}\n")
        _, out = self.lint()
        self.assertIn("EVTDESC_zzt_3 not found", out)

    def test_invalid_encoding(self) -> None:
        (self.mod / "events" / "zzt_enc.txt").write_bytes(b"x = \x81\n")
        code, out = self.lint()
        self.assertEqual(code, 1)
        self.assertIn("not valid Windows-1252", out)

    def test_package(self) -> None:
        r = run("tools/package.py", self.folder)
        self.assertEqual(r.returncode, 0, r.stderr)
        import zipfile

        out = ROOT / "dist" / f"{self.folder}.zip"
        self.addCleanup(out.unlink, missing_ok=True)
        names = zipfile.ZipFile(out).namelist()
        self.assertIn("zz_selftest.mod", names)
        self.assertIn("zz_selftest/events/zzt_events.txt", names)
        self.assertNotIn("zz_selftest/PREFIX", names)

    def test_errorlog_filter(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as f:
            f.write("[eventmanager.cpp:1]: Unknown event zzt.9\n[x.cpp:2]: unrelated\n[eventmanager.cpp:1]: Unknown event zzt.9\n")
        self.addCleanup(Path(f.name).unlink)
        r = run("tools/errorlog.py", f.name, self.folder)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("2x", r.stdout)
        self.assertNotIn("unrelated", r.stdout)


if __name__ == "__main__":
    unittest.main()
