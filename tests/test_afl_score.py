"""Allied Fleets: the lender's score is written twice, as the ai_acceptance a player sees on Ask for
Ships and Hire Ships (decisions/afl_decisions.txt) and as the effects by which an AI lender answers
(common/scripted_effects/afl_score_effects.txt). The game can't compute one from the other, so this
checks that the two give the same base, reasons and values, and that each reason has its trigger and
its localisation (mods/allied_fleets/README.md, "The lender's score")."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import xref  # noqa: E402

MOD = ROOT / "mods" / "allied_fleets"
# decision -> the scripted effect by which an AI lender answers it
PAIRS = {"afl_ask_war_loan": "afl_war_loan_score_effect", "afl_hire_ships": "afl_charter_score_effect"}


def nodes(path: Path) -> list[xref.Node]:
    return xref.parse(path.read_text(encoding="latin-1"))


def top(path: Path) -> dict[str, xref.Node]:
    return {n.key: n for n in nodes(path)}


def effect_score(effects: dict[str, xref.Node], name: str) -> tuple[int | None, set[tuple[str, int]]]:
    """(base, {(trigger, value)}) of a score effect, following calls to other score effects."""
    base, reasons = None, set()
    for n in effects[name].value:
        if n.key == "set_variable" and xref.child(n, "which") == "afl_score":
            base = int(xref.child(n, "value"))
        elif n.key == "if":
            limit = next(c for c in n.value if c.key == "limit")
            change = next(c for c in n.value if c.key == "change_variable")
            (trigger,) = [c.key for c in limit.value if c.value == "yes"]
            reasons.add((trigger, int(xref.child(change, "value"))))
        elif n.key in effects and n.value == "yes":
            reasons |= effect_score(effects, n.key)[1]
    return base, reasons


def acceptance(decision: xref.Node) -> tuple[int, set[tuple[str, int]], set[str]]:
    """(factor, {(trigger, value)}, {localisation keys}) of a decision's ai_acceptance."""
    block = next(c for c in decision.value if c.key == "ai_acceptance")
    reasons, keys = set(), set()
    for m in (c for c in block.value if c.key == "additive_modifier"):
        (trigger,) = [c.key for c in m.value if c.key not in ("value", "localisation_key")]
        reasons.add((trigger, int(xref.child(m, "value"))))
        keys.add(xref.child(m, "localisation_key"))
    return int(xref.child(block, "factor")), reasons, keys


class LenderScoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.effects = top(MOD / "common/scripted_effects/afl_score_effects.txt")
        decisions = top(MOD / "decisions/afl_decisions.txt")["targeted_decisions"].value
        self.decisions = {d.key: d for d in decisions}
        self.triggers = set()
        for f in sorted((MOD / "common/scripted_triggers").glob("*.txt")):
            self.triggers |= {n.key for n in nodes(f)}
        self.loc = xref.loc_keys(MOD / "localisation")

    def test_decisions_match_effects(self) -> None:
        for decision, effect in PAIRS.items():
            with self.subTest(decision=decision):
                factor, shown, _ = acceptance(self.decisions[decision])
                base, answered = effect_score(self.effects, effect)
                self.assertEqual(factor, base, "ai_acceptance factor vs the effect's starting afl_score")
                self.assertEqual(sorted(shown - answered), [], "shown to players, missing from the AI's answer")
                self.assertEqual(sorted(answered - shown), [], "in the AI's answer, not shown to players")

    def test_reasons_defined(self) -> None:
        for decision in PAIRS:
            with self.subTest(decision=decision):
                _, shown, keys = acceptance(self.decisions[decision])
                self.assertEqual(sorted(t for t, _ in shown if t not in self.triggers), [], "undefined triggers")
                self.assertEqual(sorted(k for k in keys if k not in self.loc), [], "missing localisation")


if __name__ == "__main__":
    unittest.main()
