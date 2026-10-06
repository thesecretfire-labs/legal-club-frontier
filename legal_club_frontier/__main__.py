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


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--samples", type=int, default=4000)
    ap.add_argument("--tolerance", action="store_true", help="judge legality with the rules' manufacturing tolerances added")
    ap.add_argument("--top", type=int, default=12, help="how many frontier designs to print")
    ap.add_argument("--record-dir", default=str(HERE.parent / "runs"))
    a = ap.parse_args(argv)

    t0 = time.time()
    result = search.run(seed=a.seed, n_samples=a.samples, allow_tolerance=a.tolerance)
    elapsed = time.time() - t0

    print(f"sampled {result['sampled']} designs in a box wider than the rules; {result['rejected_as_illegal']} rejected as illegal; "
          f"{result['frontier_size']} on the legal Pareto frontier ({elapsed:.1f} s, seed {a.seed})")
    print()
    print(f"{'loft':>5} {'len in':>6} {'cc':>5} {'MOI':>6} {'CT us':>5} | {'ball m/s':>8} {'forgive':>7} {'carry m':>7} {'control':>7}")
    for e in result["frontier"][: a.top]:
        d, o = e["design"], e["objectives"]
        print(f"{d['loft_deg']:5.1f} {d['shaft_length_in']:6.1f} {d['head_volume_cc']:5.0f} {d['moment_of_inertia_gcm2']:6.0f} {d['characteristic_time_us']:5.0f} | "
              f"{o['ball_speed_center_mps']:8.1f} {o['forgiveness']:7.3f} {o['carry_proxy_m']:7.1f} {o['control']:7.3f}")
    if result["frontier_size"] > a.top:
        print(f"... {result['frontier_size'] - a.top} more on the frontier (see the run record)")

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
        **result,
    }
    out = pathlib.Path(a.record_dir); out.mkdir(parents=True, exist_ok=True)
    path = out / f"run-{time.strftime('%Y%m%d-%H%M%S')}-seed{a.seed}.json"
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print()
    print(f"run record: {path}")
    print("acceptance: NOT REVIEWED (the program never marks its own output accepted)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
