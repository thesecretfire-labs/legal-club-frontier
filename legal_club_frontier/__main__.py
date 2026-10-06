"""`python -m legal_club_frontier`: run the search, print the frontier, write a run record.

The run record is the part most tools skip. It names the seed, the rule-table fingerprint the designs were
judged by, the model file's hash, and the counts (how many sampled, how many rejected as illegal, how many
on the frontier), so a result can be re-checked later without trusting the printout. Command success is
not acceptance: the record's `acceptance` field is always "NOT REVIEWED" when written by this program, and
only a person changes it.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess
import sys
import time

from . import model, rules, search

HERE = pathlib.Path(__file__).resolve().parent


def file_sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def git_commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=HERE.parent, capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return "not a git checkout"


def _parse_loft(raw):
    try:
        value = float(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(f"--loft must be 8.5 or 10 (or 10.0), got {raw!r}")
    if value not in (8.5, 10.0):
        raise argparse.ArgumentTypeError(f"--loft must be 8.5 or 10 (or 10.0), got {raw!r}")
    return value


def _print_and_record(a, loft):
    t0 = time.time()
    result = search.run(seed=a.seed, n_samples=a.samples, allow_tolerance=a.tolerance, loft_deg=loft,
                         swing_speed_ref_mps=a.swing_speed_mps,
                         materials_path=a.materials_csv, cost_path=a.cost_csv,
                         production_time_path=a.production_time_csv, machining_accuracy_path=a.machining_accuracy_csv)
    elapsed = time.time() - t0

    heading = f"-- {loft:g}-degree driver --" if loft is not None else None
    if heading:
        print(heading)
    print(f"sampled {result['sampled']} designs in a box wider than the rules; {result['rejected_as_illegal']} rejected as illegal; "
          f"{result['rejected_as_infeasible']} rejected as infeasible for the active material; "
          f"{result['frontier_size']} on the legal Pareto frontier ({elapsed:.1f} s, seed {a.seed})")
    if result["placeholder_outlets"]:
        names = ", ".join(f"{name}=PLACEHOLDER" for name in ("materials", "cost", "production_time", "machining_accuracy"))
        print(f"outlets in use: {names} (pass --materials-csv etc. to replace)")
    print()
    print(f"{'loft':>5} {'len in':>6} {'cc':>5} {'MOI':>6} {'CT us':>5} | {'ball m/s':>8} {'forgive':>7} {'carry m':>7} {'cost $':>7} {'lead d':>6} {'control':>7}")
    for e in result["frontier"][: a.top]:
        d, o = e["design"], e["objectives"]
        print(f"{d['loft_deg']:5.1f} {d['shaft_length_in']:6.1f} {d['head_volume_cc']:5.0f} {d['moment_of_inertia_gcm2']:6.0f} {d['characteristic_time_us']:5.0f} | "
              f"{o['ball_speed_center_mps']:8.1f} {o['forgiveness']:7.3f} {o['carry_proxy_m']:7.1f} {o['unit_cost_usd']:7.1f} {o['lead_time_days']:6.1f} {e['control']:7.3f}")
    if result["frontier_size"] > a.top:
        print(f"... {result['frontier_size'] - a.top} more on the frontier (see the run record)")

    for e in result["frontier"]:
        e["legality_margins"] = rules.legality_margins(e["design"], allow_tolerance=a.tolerance, shop_tolerances=result["shop_tolerances"])

    record = {
        "written": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "command": " ".join(sys.argv[1:]) or "(defaults)",
        "code_commit": git_commit(),
        "rules_fingerprint": rules.rules_fingerprint(),
        "rules_verify_date": rules.verify_date,
        "model_sha256": file_sha256(model.__file__),
        "elapsed_s": round(elapsed, 3),
        "acceptance": "NOT REVIEWED",
        "acceptance_note": "written by the program; a person sets this after looking at the frontier and the model's assumptions",
        "shop_tolerances_applied": result["shop_tolerances"],
        "machining_accuracy_source": result["outlets"]["machining_accuracy"],
        **result,
    }
    out = pathlib.Path(a.record_dir); out.mkdir(parents=True, exist_ok=True)
    suffix = f"-loft{loft}" if loft is not None else ""
    path = out / f"run-{time.strftime('%Y%m%d-%H%M%S')}-seed{a.seed}{suffix}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print()
    print(f"run record: {path}")
    print("acceptance: NOT REVIEWED (the program never marks its own output accepted)")
    print()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--samples", type=int, default=4000)
    ap.add_argument("--tolerance", action="store_true", help="judge legality with the rules' manufacturing tolerances added")
    ap.add_argument("--top", type=int, default=12, help="how many frontier designs to print")
    ap.add_argument("--record-dir", default=str(HERE.parent / "runs"))
    ap.add_argument("--loft", type=_parse_loft, default=None,
                     help="fix loft to 8.5 or 10 (or 10.0) degrees; omit to run both and print both tables")
    ap.add_argument("--swing-speed-mps", type=float, default=45.0,
                     help="reference clubhead speed for a 45-inch driver; lower loft suits a higher value")
    ap.add_argument("--materials-csv", default=None, help="path to a materials outlet CSV; omit to use the bundled placeholder")
    ap.add_argument("--cost-csv", default=None, help="path to a cost outlet CSV; omit to use the bundled placeholder")
    ap.add_argument("--production-time-csv", default=None, help="path to a production-time outlet CSV; omit to use the bundled placeholder")
    ap.add_argument("--machining-accuracy-csv", default=None, help="path to a machining-accuracy outlet CSV; omit to use the bundled placeholder")
    a = ap.parse_args(argv)

    if a.loft is None:
        for loft in (8.5, 10.0):
            _print_and_record(a, loft)
    else:
        _print_and_record(a, a.loft)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
