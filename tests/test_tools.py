import contextlib
import io
import os
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

    def test_github_annotations(self) -> None:
        (self.mod / "events" / "zzt_dup.txt").write_text("character_event = {\n\tid = zzt.1\n}\n")
        r = subprocess.run([sys.executable, "tools/lint.py", self.folder], cwd=ROOT, capture_output=True, text=True,
                           env={**os.environ, "GITHUB_ACTIONS": "true"})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertRegex(r.stdout, r"(?m)^::error file=mods/zz_selftest/events/zzt_[a-z]+\.txt(,line=\d+)?::.*duplicate event id zzt\.1")
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}
        r = subprocess.run([sys.executable, "tools/lint.py", self.folder], cwd=ROOT, capture_output=True, text=True, env=env)
        self.assertNotIn("::error", r.stdout)

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
    def test_xref_fired_event_missing(self) -> None:
        (self.mod / "events" / "zzt_x.txt").write_text(
            "namespace = zzt\ncharacter_event = {\n\tid = zzt.2\n\tdesc = EVTDESC_zzt_1\n"
            "\toption = { name = EVTOPTA_zzt_1 character_event = { id = zzt.99 } }\n}\n")
        code, out = self.lint()
        self.assertEqual(code, 1, out)
        self.assertIn("fires event zzt.99", out)

    def test_xref_warnings(self) -> None:
        (self.mod / "events" / "zzt_x.txt").write_text(
            "namespace = zzt\ncharacter_event = {\n\tid = zzt.2\n\tdesc = EVTDESC_zzt_1\n"
            "\tis_triggered_only = yes\n"
            "\toption = { name = EVTOPTA_zzt_1 set_character_flag = zzt_set_only\n"
            "\t\tevent_target:zzt_nowhere = { has_character_flag = zzt_never_set }\n"
            "\t\tcharacter_event = { id = zzt.1 } }\n}\n")
        (self.mod / "decisions" / "zzt_decisions.txt").write_text(
            "decisions = {\n\tzzt_do_thing = {\n\t\teffect = { has_earmarked_regiments = zzt_nomark }\n\t}\n}\n")
        code, out = self.lint()
        self.assertEqual(code, 0, out)
        for needle in ("zzt.2 is_triggered_only but nothing", "zzt_set_only is set but never",
                       "zzt_never_set is checked or cleared but never set", "event_target:zzt_nowhere",
                       "no localisation key zzt_do_thing", "earmark zzt_nomark"):
            self.assertIn(needle, out)
        self.assertNotIn("zzt.1 is_triggered_only", out)

    def test_xref_parse(self) -> None:
        import xref
        nodes = xref.parse('a = { b = "x y" # c = 1\n d >= 2 { 1 2 } }')
        self.assertEqual(nodes[0].key, "a")
        inner = nodes[0].value
        self.assertEqual([(n.key, n.value) for n in inner[:2]], [("b", "x y"), ("d", "2")])
        self.assertEqual([n.key for n in inner[2].value], ["1", "2"])


class CwtoolsCheckTest(unittest.TestCase):
    def test_skips_without_cwtools(self) -> None:
        import cwtools_check
        from unittest import mock
        with mock.patch("shutil.which", return_value=None), mock.patch("builtins.print") as p:
            self.assertEqual(cwtools_check.main(["--strict", "_template"]), 0)
        self.assertIn("skipped", p.call_args[0][0])


if __name__ == "__main__":
    unittest.main()


class HarnessTest(unittest.TestCase):
    def test_instrument(self) -> None:
        import harness

        text = (
            "namespace = zzt\n"
            "# character_event = { id = zzt.0 }\n"
            "character_event = {\n\tid = zzt.1\n\tdesc = \"a { b\"\n\timmediate = {\n\t\twealth = 1\n\t}\n\toption = { name = OK }\n}\n"
            "province_event = { id = zzt.2 option = { name = OK } }\n"
            "narrative_event = {\n\tid = zzt.3\n\toption = { name = OK immediate = { } }\n}\n"
        )
        out, ids = harness.instrument(text)
        self.assertEqual(ids, ["zzt.1", "zzt.2", "zzt.3"])
        self.assertIn('immediate = {\n\t\tlog = "CK2TEST fired zzt.1"', out)
        self.assertIn('immediate = { log = "CK2TEST fired zzt.2" }', out)
        # zzt.3's only immediate is inside an option, so the event gets its own.
        self.assertRegex(out, r'option = \{ name = OK immediate = \{ \} \}\n\timmediate = \{ log = "CK2TEST fired zzt.3" \}')
        self.assertNotIn("zzt.0", ids)
        self.assertEqual(out.count("CK2TEST"), 3)
        self.assertEqual(out.count("{") - out.count("}"), text.count("{") - text.count("}"))

    def test_report(self) -> None:
        mod, tests = ROOT / "mods" / "zz_harnesstest", ROOT / "tests" / "game" / "zz_harnesstest"
        for d in (mod, tests):
            self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        (mod / "events").mkdir(parents=True)
        (mod / "events" / "zzh_events.txt").write_text(
            "namespace = zzh\ncharacter_event = { id = zzh.1 }\ncharacter_event = { id = zzh.2 }\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "game.log"

            def report(*lines: str) -> subprocess.CompletedProcess:
                log.write_text("".join(f"[effectimplementation.cpp:1]: {line}\n" for line in lines))
                return run("tools/harness.py", "report", "zz_harnesstest", str(log))

            # No tests: events are only counted.
            r = report("CK2TEST fired zzh.1")
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("events fired: 1 of 2", r.stdout)
            tests.mkdir(parents=True)
            r = report("CK2TEST fired zzh.1", "CK2TEST pass a")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("never fired: zzh.2", r.stdout)
            self.assertIn("did not log CK2TEST done", r.stdout)
            done = ("CK2TEST fired zzh.1", "CK2TEST fired zzh.2", "CK2TEST pass a", "CK2TEST done")
            r = report(*done)
            self.assertEqual(r.returncode, 0, r.stdout)
            r = report(*done, "CK2TEST fail b")
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("FAIL: b", r.stdout)
