"""Inverse design: constraints and objectives in, a Pareto frontier of legal designs out.

The shape is the whole point, and it is generic: (1) a design space with explicit bounds, (2) a legality
predicate read from a cited rule table, (3) an objective function, (4) a non-dominated sort. The golf
driver is only the example that makes the shape visible. Swap `rules.py` and `model.py` and the search
does not change.

The search is a seeded all-to-all pass: sample the box uniformly, keep what is legal, evaluate, then run a
few rounds of local perturbation around the current frontier so the frontier fills in. Deterministic for
a given seed, which is what lets the tests pin its behaviour.
"""
import numpy as np

from .model import OBJECTIVES, evaluate
from .rules import legality

# The design box. Bounds are deliberately WIDER than the rules on every ruled field, so that the legality
# predicate is doing real work (if the box already excluded every illegal club, the rules would be decorative).
BOUNDS = {
    "loft_deg":               (6.0, 16.0),
    "shaft_length_in":        (40.0, 50.0),
    "head_volume_cc":         (380.0, 500.0),
    "head_mass_g":            (185.0, 215.0),
    "moment_of_inertia_gcm2": (2500.0, 6500.0),
    "characteristic_time_us": (150.0, 280.0),
    "heel_to_toe_in":         (4.2, 5.4),
    "face_to_back_in":        (3.8, 5.6),
    "sole_to_crown_in":       (2.2, 3.1),
    "groove_width_in":        (0.020, 0.045),
    "groove_depth_in":        (0.010, 0.026),
}
FIELDS = tuple(BOUNDS)


def sample_box(rng, n):
    lo = np.array([BOUNDS[f][0] for f in FIELDS])
    hi = np.array([BOUNDS[f][1] for f in FIELDS])
    return lo + rng.random((n, len(FIELDS))) * (hi - lo)


def to_design(row):
    return {f: float(v) for f, v in zip(FIELDS, row)}


def non_dominated(points):
    """Indices of the Pareto-optimal rows of `points` (every objective higher-is-better). O(n^2), fine at this size."""
    keep = []
    for i, p in enumerate(points):
        dominated = False
        for j, q in enumerate(points):
            if i != j and np.all(q >= p) and np.any(q > p):
                dominated = True
                break
        if not dominated:
            keep.append(i)
    return keep


def run(seed=0, n_samples=4000, refine_rounds=3, refine_per_point=20, allow_tolerance=False):
    """Returns a dict: the legal frontier designs with their objectives, plus the counts that make the run auditable."""
    rng = np.random.default_rng(seed)
    rows = sample_box(rng, n_samples)
    sampled = len(rows)
    legal_rows = [r for r in rows if legality(to_design(r), allow_tolerance=allow_tolerance)[0]]
    rejected = sampled - len(legal_rows)
    pool = np.array(legal_rows)
    for _ in range(refine_rounds):
        scores = np.array([[evaluate(to_design(r))[o] for o in OBJECTIVES] for r in pool])
        front = pool[non_dominated(scores)]
        lo = np.array([BOUNDS[f][0] for f in FIELDS]); hi = np.array([BOUNDS[f][1] for f in FIELDS])
        children = []
        for r in front:
            jitter = rng.normal(0.0, 0.03, size=(refine_per_point, len(FIELDS))) * (hi - lo)
            cand = np.clip(r + jitter, lo, hi)
            children.extend(c for c in cand if legality(to_design(c), allow_tolerance=allow_tolerance)[0])
        pool = np.vstack([front, np.array(children)]) if children else front
    scores = np.array([[evaluate(to_design(r))[o] for o in OBJECTIVES] for r in pool])
    idx = non_dominated(scores)
    frontier = [{"design": to_design(pool[i]), "objectives": dict(zip(OBJECTIVES, map(float, scores[i])))} for i in idx]
    frontier.sort(key=lambda e: -e["objectives"]["carry_proxy_m"])
    return {
        "seed": seed, "sampled": sampled, "rejected_as_illegal": rejected, "legal_after_sampling": len(legal_rows),
        "allow_tolerance": allow_tolerance, "frontier_size": len(frontier), "frontier": frontier,
    }
