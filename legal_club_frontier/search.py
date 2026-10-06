"""Inverse design: constraints and objectives in, a Pareto frontier of legal designs out.

The shape is the whole point, and it is generic: (1) a design space with explicit bounds, (2) a legality
predicate read from a cited rule table, (3) an objective function, (4) a non-dominated sort. The golf
driver is only the example that makes the shape visible. Swap `rules.py` and `model.py` and the search
does not change.

The search is a seeded all-to-all pass: sample the box uniformly, keep what is legal, evaluate, then run a
few rounds of local perturbation around the current frontier so the frontier fills in. Deterministic for
a given seed, which is what lets the tests pin its behaviour.

Outlets (`outlets.py`) plug in four CSV datasets: materials, cost, production_time, machining_accuracy.
Any outlet path left `None` loads its bundled placeholder; the run never fails for an absent outlet. The
materials/cost/production_time outlets are "one profile per file" -- the adapter convention is that the
first data row is the active profile. The machining_accuracy outlet is long-format: every row whose
`shop_id` equals the first `shop_id` seen is collected into a `{field_name: shop_tolerance}` dict and
passed to every `legality()` call, tightening the bound a design must clear before it reaches that shop.
"""
import numpy as np

from .model import OBJECTIVES, OBJECTIVE_DIRECTIONS, SWING_SPEED_REF_MPS, dispersion_proxy, evaluate, min_feasible_head_mass_g
from .outlets import load_all_outlets
from .rules import legality

# The design box. Bounds are deliberately WIDER than the rules on every ruled field, so that the legality
# predicate is doing real work (if the box already excluded every illegal club, the rules would be decorative).
# `loft_deg`'s bound here stays a legacy free-search range: the two-driver CLI (`--loft 8.5` / `--loft 10`)
# fixes loft per column via `run(loft_deg=...)` rather than removing or narrowing this bound.
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


def _active_profile_row(rows, numeric_fields):
    """The adapter convention for materials/cost/production_time: the first data row is the active profile."""
    row = dict(rows[0])
    for f in numeric_fields:
        row[f] = float(row[f])
    return row


def _shop_tolerances(rows):
    """Every row whose shop_id equals the first shop_id seen, collected into {field_name: shop_tolerance}."""
    if not rows:
        return {}
    shop_id = rows[0]["shop_id"]
    return {r["field_name"]: float(r["shop_tolerance"]) for r in rows if r["shop_id"] == shop_id}


def run(seed=0, n_samples=4000, refine_rounds=3, refine_per_point=20, allow_tolerance=False,
        loft_deg=None, swing_speed_ref_mps=SWING_SPEED_REF_MPS,
        materials_path=None, cost_path=None, production_time_path=None, machining_accuracy_path=None):
    """Returns a dict: the legal, feasible frontier designs with their objectives, plus the counts that
    make the run auditable, plus which outlets were placeholders and which shop tolerances were applied."""
    rng = np.random.default_rng(seed)
    rows = sample_box(rng, n_samples)
    if loft_deg is not None:
        rows[:, FIELDS.index("loft_deg")] = loft_deg
    sampled = len(rows)

    data_by_outlet, meta_by_outlet, placeholder_outlet_names = load_all_outlets(
        materials_path=materials_path, cost_path=cost_path,
        production_time_path=production_time_path, machining_accuracy_path=machining_accuracy_path)
    material_row = _active_profile_row(data_by_outlet["materials"], ("density_g_cm3", "min_wall_thickness_mm"))
    cost_row = _active_profile_row(data_by_outlet["cost"], ("material_cost_usd_per_g", "machining_cost_usd_per_cc_removed", "fixed_assembly_cost_usd"))
    production_row = _active_profile_row(data_by_outlet["production_time"], ("base_lead_time_days", "machining_minutes_per_cc"))
    shop_tolerances = _shop_tolerances(data_by_outlet["machining_accuracy"])

    def _legal(design):
        return legality(design, allow_tolerance=allow_tolerance, shop_tolerances=shop_tolerances)[0]

    def _feasible(design):
        min_mass = min_feasible_head_mass_g(design["head_volume_cc"], material_row["density_g_cm3"], material_row["min_wall_thickness_mm"])
        return design["head_mass_g"] >= min_mass

    legal_rows = [r for r in rows if _legal(to_design(r))]
    rejected_as_illegal = sampled - len(legal_rows)
    feasible_rows = [r for r in legal_rows if _feasible(to_design(r))]
    rejected_as_infeasible = len(legal_rows) - len(feasible_rows)

    pool = np.array(feasible_rows) if feasible_rows else np.empty((0, len(FIELDS)))
    sign = np.array([1.0 if OBJECTIVE_DIRECTIONS[o] == "max" else -1.0 for o in OBJECTIVES])

    def _evaluate(r):
        d = to_design(r)
        return evaluate(d, swing_speed_ref_mps=swing_speed_ref_mps, min_wall_thickness_mm=material_row["min_wall_thickness_mm"],
                         cost_row=cost_row, production_row=production_row)

    lo = np.array([BOUNDS[f][0] for f in FIELDS]); hi = np.array([BOUNDS[f][1] for f in FIELDS])
    for _ in range(refine_rounds):
        if len(pool) == 0:
            break
        scores = np.array([[_evaluate(r)[o] for o in OBJECTIVES] for r in pool])
        front = pool[non_dominated(scores * sign)]
        children = []
        for r in front:
            jitter = rng.normal(0.0, 0.03, size=(refine_per_point, len(FIELDS))) * (hi - lo)
            cand = np.clip(r + jitter, lo, hi)
            if loft_deg is not None:
                cand[:, FIELDS.index("loft_deg")] = loft_deg
            for c in cand:
                cd = to_design(c)
                if _legal(cd) and _feasible(cd):
                    children.append(c)
        pool = np.vstack([front, np.array(children)]) if children else front

    if len(pool) == 0:
        frontier = []
    else:
        scores = np.array([[_evaluate(r)[o] for o in OBJECTIVES] for r in pool])
        idx = non_dominated(scores * sign)
        frontier = []
        for i in idx:
            d = to_design(pool[i])
            frontier.append({
                "design": d,
                "objectives": dict(zip(OBJECTIVES, map(float, scores[i]))),
                "control": 1.0 - dispersion_proxy(d["shaft_length_in"], d["moment_of_inertia_gcm2"]),
            })
        frontier.sort(key=lambda e: -e["objectives"]["carry_proxy_m"])

    return {
        "seed": seed, "sampled": sampled, "rejected_as_illegal": rejected_as_illegal,
        "legal_after_sampling": len(legal_rows), "rejected_as_infeasible": rejected_as_infeasible,
        "allow_tolerance": allow_tolerance, "loft_deg": loft_deg, "swing_speed_ref_mps": swing_speed_ref_mps,
        "frontier_size": len(frontier), "frontier": frontier,
        "outlets": meta_by_outlet, "placeholder_outlets": placeholder_outlet_names,
        "shop_tolerances": shop_tolerances,
    }
