"""The acceptance harness: thirteen checks, three of them on inputs broken on purpose, plus a mutation proof.

The idea this file exists to show: a program exiting 0 is not the same fact as the work being right, and a
test suite that only ever sees good inputs cannot tell the difference. So:

  * Three designs are illegal on purpose (a 470 cc head, a 49-inch shaft, a 300-microsecond face). The
    legality predicate MUST refuse each one. If it ever accepts one, the harness fails. These are the
    negative controls.
  * The mutation proof (`python -m tests.test_acceptance_harness --mutation-proof`) replaces the legality
    predicate with one that approves everything, re-runs the harness, and demands that the harness FAIL.
    A harness that still passes with an approve-everything predicate was never testing anything.
  * The README quotes the rule limits; a check compares every quoted number to the constant in rules.py,
    byte for byte, so a paraphrase cannot drift from its source.
  * The run record must cite the rule-table fingerprint it was judged by and must carry acceptance
    NOT REVIEWED, because the program is not allowed to accept its own output.

Run:  python -m unittest tests.test_acceptance_harness -v
      python -m tests.test_acceptance_harness --mutation-proof
"""
import json
import pathlib
import re
import sys
import unittest
from unittest import mock

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legal_club_frontier import model, rules, search  # noqa: E402

LEGAL_REFERENCE = {
    "loft_deg": 10.5, "shaft_length_in": 45.5, "head_volume_cc": 455.0, "head_mass_g": 200.0,
    "moment_of_inertia_gcm2": 5600.0, "characteristic_time_us": 235.0, "heel_to_toe_in": 4.9,
    "face_to_back_in": 4.6, "sole_to_crown_in": 2.6, "groove_width_in": 0.030, "groove_depth_in": 0.018,
}

# the negative controls: each differs from the legal reference in exactly one ruled field
BROKEN_ON_PURPOSE = {
    "head too large (470 cc)": {**LEGAL_REFERENCE, "head_volume_cc": 470.0},
    "shaft too long (49 in)": {**LEGAL_REFERENCE, "shaft_length_in": 49.0},
    "face too springy (300 us)": {**LEGAL_REFERENCE, "characteristic_time_us": 300.0},
}


class AcceptanceHarness(unittest.TestCase):

    # ── the rule table itself
    def test_01_every_limit_names_its_rule(self):
        for l in rules.LIMITS:
            self.assertRegex(l.rule, r"^Part 2, Rule \d", f"{l.name} has no rule citation")

    def test_02_rules_fingerprint_is_stable(self):
        self.assertEqual(rules.rules_fingerprint(), rules.rules_fingerprint())
        self.assertEqual(len(rules.rules_fingerprint()), 64)

    def test_03_readme_quotes_match_the_rule_table(self):
        """The README's quoted limits are compared to rules.py. A paraphrase that drifts goes red here."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        table = re.search(r"<!-- rules-table-start -->(.*?)<!-- rules-table-end -->", readme, re.S)
        self.assertIsNotNone(table, "README has no rules table between the markers")
        quoted = dict(re.findall(r"^\| `([a-z_0-9]+)` \| ([0-9.]+) ", table.group(1), re.M))
        self.assertEqual(set(quoted), {l.name for l in rules.LIMITS}, "README table and rules.py name different limits")
        for l in rules.LIMITS:
            self.assertEqual(quoted[l.name], f"{l.value:g}", f"README quotes {quoted[l.name]} for {l.name}; rules.py says {l.value:g}")

    # ── the legality predicate on good input
    def test_04_legal_reference_is_legal(self):
        legal, reasons = rules.legality(LEGAL_REFERENCE)
        self.assertTrue(legal, reasons)

    def test_05_tolerance_reading_is_looser_never_tighter(self):
        d = {**LEGAL_REFERENCE, "head_volume_cc": 465.0}       # over the limit, inside the 10 cc tolerance
        self.assertFalse(rules.legality(d)[0])
        self.assertTrue(rules.legality(d, allow_tolerance=True)[0])

    # ── the negative controls: broken input MUST be refused by the same predicate
    def test_06_control_head_too_large_is_refused(self):
        legal, reasons = rules.legality(BROKEN_ON_PURPOSE["head too large (470 cc)"])
        self.assertFalse(legal, "a 470 cc head was accepted"); self.assertTrue(any("head_volume_cc" in r for r in reasons))

    def test_07_control_shaft_too_long_is_refused(self):
        legal, reasons = rules.legality(BROKEN_ON_PURPOSE["shaft too long (49 in)"])
        self.assertFalse(legal, "a 49-inch shaft was accepted"); self.assertTrue(any("shaft_length_in" in r for r in reasons))

    def test_08_control_face_too_springy_is_refused(self):
        legal, reasons = rules.legality(BROKEN_ON_PURPOSE["face too springy (300 us)"])
        self.assertFalse(legal, "a 300 us face was accepted"); self.assertTrue(any("characteristic_time_us" in r for r in reasons))

    # ── the model
    def test_09_model_objectives_are_finite_and_named(self):
        o = model.evaluate(LEGAL_REFERENCE)
        self.assertEqual(tuple(o), model.OBJECTIVES)
        self.assertTrue(all(np.isfinite(v) for v in o.values()))

    def test_10_more_inertia_means_more_forgiveness(self):
        lo = model.evaluate({**LEGAL_REFERENCE, "moment_of_inertia_gcm2": 3000.0})["forgiveness"]
        hi = model.evaluate({**LEGAL_REFERENCE, "moment_of_inertia_gcm2": 5800.0})["forgiveness"]
        self.assertGreater(hi, lo)

    # ── the search
    def test_11_search_is_deterministic_for_a_seed(self):
        a = search.run(seed=3, n_samples=600, refine_rounds=1)
        b = search.run(seed=3, n_samples=600, refine_rounds=1)
        self.assertEqual(a["frontier"], b["frontier"])

    def test_12_every_frontier_design_is_legal_and_none_is_dominated(self):
        r = search.run(seed=1, n_samples=800, refine_rounds=1)
        self.assertGreater(r["frontier_size"], 0)
        self.assertGreater(r["rejected_as_illegal"], 0, "the box never produced an illegal design, so the rules were decorative")
        for e in r["frontier"]:
            self.assertTrue(rules.legality(e["design"])[0], e["design"])
        pts = np.array([[e["objectives"][o] for o in model.OBJECTIVES] for e in r["frontier"]])
        self.assertEqual(len(search.non_dominated(pts)), len(pts), "a dominated design is on the frontier")

    # ── the record
    def test_13_run_record_cites_its_rules_and_never_accepts_itself(self):
        import contextlib, io
        from legal_club_frontier.__main__ import main
        out = ROOT / "runs" / "_harness"
        with contextlib.redirect_stdout(io.StringIO()):
            main(["--samples", "400", "--record-dir", str(out), "--top", "1"])
        rec = json.loads(sorted(out.glob("run-*.json"))[-1].read_text(encoding="utf-8"))
        self.assertEqual(rec["rules_fingerprint"], rules.rules_fingerprint())
        self.assertEqual(rec["acceptance"], "NOT REVIEWED")
        for p in out.glob("run-*.json"):
            p.unlink()
        out.rmdir()


def mutation_proof():
    """Replace the legality predicate with one that approves everything; the harness MUST fail."""
    approve_all = lambda design, allow_tolerance=False: (True, [])
    with mock.patch.object(rules, "legality", approve_all), mock.patch.object(search, "legality", approve_all):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceHarness)
        result = unittest.TextTestRunner(stream=open(pathlib.Path.cwd() / "runs" / "mutation-proof-last-run.log", "w"), verbosity=0).run(suite)
    failed = {t.id().rsplit(".", 1)[-1] for t, _ in result.failures + result.errors}
    expected = {"test_06_control_head_too_large_is_refused", "test_07_control_shaft_too_long_is_refused",
                "test_08_control_face_too_springy_is_refused", "test_05_tolerance_reading_is_looser_never_tighter"}
    caught = expected & failed
    print(f"approve-everything mutant: {len(caught)} of {len(expected)} checks that must catch it did catch it")
    for name in sorted(expected):
        print(("  caught by " if name in caught else "  MISSED by ") + name)
    if caught != expected:
        print("MUTATION PROOF FAILED: the harness let an approve-everything predicate through")
        return 1
    print("Mutation proof PASS: a harness that only passes on honest predicates.")
    return 0


if __name__ == "__main__":
    if "--mutation-proof" in sys.argv:
        (pathlib.Path.cwd() / "runs").mkdir(exist_ok=True)
        raise SystemExit(mutation_proof())
    unittest.main()
