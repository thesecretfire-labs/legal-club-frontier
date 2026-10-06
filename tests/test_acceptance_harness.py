"""The acceptance harness: twenty-one checks, three of them on inputs broken on purpose, plus a mutation proof.

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

from legal_club_frontier import model, outlets, rules, search  # noqa: E402

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
        sign = np.array([1.0 if model.OBJECTIVE_DIRECTIONS[o] == "max" else -1.0 for o in model.OBJECTIVES])
        pts = np.array([[e["objectives"][o] for o in model.OBJECTIVES] for e in r["frontier"]])
        self.assertEqual(len(search.non_dominated(pts * sign)), len(pts), "a dominated design is on the frontier")

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

    # ── the outlets
    def test_14_every_outlet_placeholder_is_detected_and_named(self):
        for spec in outlets.OUTLETS:
            rows, meta = outlets.load_outlet(spec, path=None)
            self.assertTrue(meta["is_placeholder"], spec.name)
            self.assertEqual(meta["source_path"], str(spec.placeholder_path))

    def test_15_user_outlet_csv_missing_column_is_refused_and_names_the_column(self):
        import tempfile
        bad = "material_id,display_name,density_g_cm3,source_note,is_placeholder_data\n" \
              "placeholder_alloy,Placeholder Alloy,4.5,\"PLACEHOLDER - NOT REAL DATA, FOR WIRING AND TESTING ONLY\",TRUE\n"
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(bad)
            tmp_path = f.name
        try:
            with self.assertRaises(outlets.OutletError) as ctx:
                outlets.load_outlet(outlets.MATERIALS, path=tmp_path)
            self.assertIn("min_wall_thickness_mm", str(ctx.exception))
        finally:
            pathlib.Path(tmp_path).unlink()

    def test_16_shop_tolerance_tightens_the_legality_bound(self):
        """The shop tolerance is read from the machining-accuracy outlet, not hardcoded here, so the mutation
        proof's zero-tolerance mutant (which patches that outlet) is caught by this same test."""
        rows, _ = outlets.load_outlet(outlets.MACHINING_ACCURACY, path=None)
        shop_tolerances = {r["field_name"]: float(r["shop_tolerance"]) for r in rows if r["field_name"] == "head_volume_cc"}
        d = {**LEGAL_REFERENCE, "head_volume_cc": 458.0}
        self.assertTrue(rules.legality(d)[0], "458 cc should be legal at nominal")
        legal, reasons = rules.legality(d, shop_tolerances=shop_tolerances)
        self.assertFalse(legal, "legal at nominal but illegal once the shop tolerance is subtracted must be refused")
        self.assertTrue(any("head_volume_cc" in r for r in reasons))

    def test_17_readme_outlet_contract_table_matches_adapter_headers_byte_for_byte(self):
        """Same drift-check pattern as test_03: the README's outlets table is compared to outlets.py byte for byte."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        table = re.search(r"<!-- outlets-table-start -->(.*?)<!-- outlets-table-end -->", readme, re.S)
        self.assertIsNotNone(table, "README has no outlets table between the markers")
        quoted = dict(re.findall(r"^\| `([a-z_0-9]+)` \| `([a-z_0-9,]+)` \|", table.group(1), re.M))
        self.assertEqual(set(quoted), {spec.name for spec in outlets.OUTLETS}, "README table and outlets.py name different outlets")
        for spec in outlets.OUTLETS:
            self.assertEqual(quoted[spec.name], ",".join(spec.header),
                              f"README quotes {quoted[spec.name]} for {spec.name}; outlets.py says {','.join(spec.header)}")

    def test_18_run_record_names_which_outlets_were_placeholders(self):
        r = search.run(seed=2, n_samples=400, refine_rounds=1)
        self.assertEqual(r["placeholder_outlets"], ["materials", "cost", "production_time", "machining_accuracy"])

    def test_19_run_record_names_which_shop_tolerances_were_applied(self):
        import contextlib, io
        from legal_club_frontier.__main__ import main
        out = ROOT / "runs" / "_harness19"
        with contextlib.redirect_stdout(io.StringIO()):
            main(["--samples", "400", "--record-dir", str(out), "--top", "1"])
        rec = json.loads(sorted(out.glob("run-*.json"))[-1].read_text(encoding="utf-8"))
        self.assertIn("shop_tolerances_applied", rec)
        self.assertTrue(rec["shop_tolerances_applied"])
        for p in out.glob("run-*.json"):
            p.unlink()
        out.rmdir()

    def test_20_missing_outlet_file_path_is_refused_by_name(self):
        with self.assertRaises(outlets.OutletError) as ctx:
            outlets.load_outlet(outlets.MATERIALS, path="no/such/file.csv")
        self.assertIn("no/such/file.csv", str(ctx.exception))

    def test_21_unspecified_outlet_degrades_to_placeholder_and_search_still_runs(self):
        r = search.run(n_samples=400)
        self.assertGreater(r["frontier_size"], 0)


MACHINING_ACCURACY_FIELDS = ("head_volume_cc", "moment_of_inertia_gcm2", "characteristic_time_us", "shaft_length_in")


def mutation_proof():
    """Replace the legality predicate with one that approves everything, and separately replace the
    machining-accuracy outlet with one that always returns zero tolerances; the harness MUST fail on both."""
    approve_all = lambda design, allow_tolerance=False, shop_tolerances=None: (True, [])
    expected_approve_all = {"test_06_control_head_too_large_is_refused", "test_07_control_shaft_too_long_is_refused",
                             "test_08_control_face_too_springy_is_refused", "test_05_tolerance_reading_is_looser_never_tighter"}

    with mock.patch.object(rules, "legality", approve_all), mock.patch.object(search, "legality", approve_all):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceHarness)
        result = unittest.TextTestRunner(stream=open(pathlib.Path.cwd() / "runs" / "mutation-proof-last-run.log", "w"), verbosity=0).run(suite)
    failed_approve_all = {t.id().rsplit(".", 1)[-1] for t, _ in result.failures + result.errors}

    original_load_outlet = outlets.load_outlet

    def zero_tol(spec, path=None):
        if spec is outlets.MACHINING_ACCURACY:
            rows = [{"shop_id": "x", "shop_name": "x", "field_name": f, "shop_tolerance": "0.0", "unit": "",
                     "source_note": outlets.PLACEHOLDER_LABEL, "is_placeholder_data": "TRUE"} for f in MACHINING_ACCURACY_FIELDS]
            meta = {"outlet": "machining_accuracy", "source_path": str(spec.placeholder_path),
                    "is_placeholder": True, "row_count": len(rows), "fingerprint": "zero-tolerance-mutant"}
            return rows, meta
        return original_load_outlet(spec, path=path)

    expected_zero_tol = {"test_16_shop_tolerance_tightens_the_legality_bound"}
    with mock.patch.object(outlets, "load_outlet", zero_tol):
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(AcceptanceHarness)
        result2 = unittest.TextTestRunner(stream=open(pathlib.Path.cwd() / "runs" / "mutation-proof-last-run.log", "a"), verbosity=0).run(suite)
    failed_zero_tol = {t.id().rsplit(".", 1)[-1] for t, _ in result2.failures + result2.errors}

    expected = expected_approve_all | expected_zero_tol
    caught = (expected_approve_all & failed_approve_all) | (expected_zero_tol & failed_zero_tol)
    print(f"approve-everything mutant: {len(expected_approve_all & failed_approve_all)} of {len(expected_approve_all)} checks that must catch it did catch it")
    for name in sorted(expected_approve_all):
        print(("  caught by " if name in (expected_approve_all & failed_approve_all) else "  MISSED by ") + name)
    print(f"zero-tolerance mutant: {len(expected_zero_tol & failed_zero_tol)} of {len(expected_zero_tol)} checks that must catch it did catch it")
    for name in sorted(expected_zero_tol):
        print(("  caught by " if name in (expected_zero_tol & failed_zero_tol) else "  MISSED by ") + name)
    print(f"combined: {len(caught)} of {len(expected)} checks that must catch it did catch it")
    if caught != expected:
        print("MUTATION PROOF FAILED: the harness let a liar through")
        return 1
    print("Mutation proof PASS: a harness that only passes on honest predicates.")
    return 0


if __name__ == "__main__":
    if "--mutation-proof" in sys.argv:
        (pathlib.Path.cwd() / "runs").mkdir(exist_ok=True)
        raise SystemExit(mutation_proof())
    unittest.main()
