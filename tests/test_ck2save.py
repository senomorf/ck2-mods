import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import ck2save  # noqa: E402

SAVE = b'''CK2txt
\tversion="3.3.5.1"
\tdate="1068.1.1"
\tflags=
\t{
\t\tafl_test_started=1067.1.1
\t}
\tcharacter=
\t{
\t\t1=
\t\t{
\t\t\tbn="Caf\xe9"
\t\t\tflags=
\t\t\t{
\t\t\t\tafl_request_pending=1067.1.2
\t\t\t}
\t\t\tmd=
\t\t\t{
\t\t\t\tmodifier="afl_old_modifier"
\t\t\t}
\t\t\tnums={ 1 2 3 }
\t\t}
\t\t2=
\t\t{
\t\t\tbn="Bob"
\t\t\tdmn=
\t\t\t{
\t\t\t\tnavy=
\t\t\t\t{
\t\t\t\t\tsub_unit=
\t\t\t\t\t{
\t\t\t\t\t\ttroops={ ga=20.000 }
\t\t\t\t\t\tearmark="zz_lent"
\t\t\t\t\t\tdisband_on_peace=yes
\t\t\t\t\t}
\t\t\t\t\tsub_unit=
\t\t\t\t\t{
\t\t\t\t\t\ttroops={ ga=12.000 }
\t\t\t\t\t}
\t\t\t\t}
\t\t\t}
\t\t}
\t}
\tchecksum="abc"
}
'''


class Ck2SaveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.block = ck2save.parse(SAVE)

    def test_parse_and_get(self) -> None:
        self.assertEqual(ck2save.first(self.block, "date"), "1068.1.1")
        self.assertEqual(ck2save.first(self.block, "checksum"), "abc")
        self.assertEqual(ck2save.get(self.block, "character/*/bn"), ["Caf\xe9", "Bob"])
        self.assertEqual(len(ck2save.get(self.block, "character/*")), 2)
        self.assertEqual(ck2save.get(self.block, "character/1/nums/*"), ["1", "2", "3"])
        self.assertEqual(ck2save.get(self.block, "character/*/flags/afl_request_pending"), ["1067.1.2"])

    def test_filters_and_every(self) -> None:
        lent = "character/*/dmn/navy/sub_unit[earmark=zz_lent]"
        self.assertEqual(len(ck2save.get(self.block, lent)), 1)
        self.assertEqual(len(ck2save.get(self.block, "character/*/dmn/navy/sub_unit")), 2)
        out, failed = ck2save.run_checks(self.block, [
            f"every {lent}/troops/ga == 20",
            f"every {lent}/disband_on_peace == yes",
            "every character/*/dmn/navy/sub_unit/troops/ga >= 20",
            "every character/*/nothing == 1",
            "every character/*/bn > Bob",
        ])
        self.assertEqual(out[0], f"CK2SAVE pass every {lent}/troops/ga == 20 (1 values)")
        self.assertTrue(out[1].startswith("CK2SAVE pass"), out[1])
        self.assertIn("2 values, 1 not: 12.000", out[2])
        self.assertIn("(no values at the path)", out[3])
        self.assertTrue(out[4].startswith("CK2SAVE fail"), out[4])  # names don't order
        self.assertEqual(failed, 3)

    def test_prefixed_names(self) -> None:
        self.assertEqual(set(ck2save.prefixed(self.block, ["afl"])),
                         {"afl_test_started", "afl_request_pending", "afl_old_modifier"})

    def test_checks(self) -> None:
        out, failed = ck2save.run_checks(self.block, [
            "present afl_test_started  # a comment",
            "absent afl_gone",
            "count character/*/flags/afl_request_pending >= 1",
            "",
        ])
        self.assertEqual(failed, 0, out)
        out, failed = ck2save.run_checks(self.block, [
            "absent afl_test_started", "count character/* == 3", "frobnicate x"])
        self.assertEqual(failed, 3, out)
        self.assertTrue(all(o.startswith("CK2SAVE fail") for o in out))

    def test_dangling(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "events").mkdir()
            (Path(d) / "events" / "x.txt").write_text(
                "set_global_flag = afl_test_started\nset_character_flag = afl_request_pending\n")
            self.assertEqual(set(ck2save.dangling(self.block, "afl", d)), {"afl_old_modifier"})

    def test_zipped_save(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.ck2"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("meta", b"date=1.1.1")
                z.writestr("a.ck2", SAVE)
            self.assertEqual(ck2save.first(ck2save.load(p), "date"), "1068.1.1")


if __name__ == "__main__":
    unittest.main()
