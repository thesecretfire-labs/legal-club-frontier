"""A deliberately small performance model for a driver, so the search has something to trade off.

THIS IS A TOY. It is here to give the inverse-design search real objectives with real tensions between
them; it is not a validated golf simulator and no number it produces should be quoted as a prediction.
Every relation below is a textbook-shaped approximation, named, so a reader can see exactly what is being
assumed and swap in a better model without touching the search or the rules.

Design fields (all SI except where the rules themselves use inches):
    loft_deg, shaft_length_in, head_volume_cc, head_mass_g, moment_of_inertia_gcm2,
    characteristic_time_us, heel_to_toe_in, face_to_back_in, sole_to_crown_in,
    groove_width_in, groove_depth_in

Objectives returned by `evaluate`:
    ball_speed_center_mps   ball speed on a centred strike (max is better)
    forgiveness             ball speed retained on a 15 mm off-centre strike, as a fraction of centre (max is better)
    carry_proxy_m           a carry estimate from speed and launch, flat ground, no wind (max is better)
    unit_cost_usd           a shell-volume-proxy cost built from the active cost outlet (min is better)
    lead_time_days          a shell-volume-proxy lead time built from the active production-time outlet (min is better)
`control` (the dispersion proxy) is still computed and reported, but is excluded from `OBJECTIVES`; see
`OBJECTIVE_DIRECTIONS` for which way each of the five sortable objectives points.
"""
import math

BALL_MASS_G = 45.93           # Rules of Golf, Equipment Rules Part 4: ball mass not greater than 45.93 g
SWING_SPEED_REF_MPS = 45.0    # a strong amateur's clubhead speed with a 45-inch driver, used as the reference
LENGTH_REF_IN = 45.0


def clubhead_speed(shaft_length_in, swing_speed_ref_mps=SWING_SPEED_REF_MPS):
    """Clubhead speed scales roughly with the square root of length for the same swing (longer arc, same effort)."""
    return swing_speed_ref_mps * math.sqrt(shaft_length_in / LENGTH_REF_IN)


def peak_loft_deg(clubhead_speed_mps):
    """Optimal loft falls as clubhead speed rises (anchors, both approximations, not a fit to real
    launch-monitor data: about 13 degrees near a 45 m/s reference swing, about 9.9 degrees near 52 m/s).
    Linear in clubhead speed at 0.45 degrees of loft per m/s."""
    return 13.0 - 0.45 * (clubhead_speed_mps - SWING_SPEED_REF_MPS)


def coefficient_of_restitution(characteristic_time_us):
    """Map characteristic time to COR on a straight line through two published anchors (CT 239 us ~ COR 0.830,
    CT 0 ~ COR 0.78 for a rigid face). An approximation, named as one."""
    return 0.78 + 0.05 * (characteristic_time_us / 239.0)


def smash_factor(cor, head_mass_g, loft_deg):
    """Collision of a head of mass M with a ball of mass m at COR e, reduced by loft (the oblique-impact cosine)."""
    M, m = head_mass_g, BALL_MASS_G
    return (1.0 + cor) * M / (M + m) * math.cos(math.radians(loft_deg)) ** 0.5


def offcentre_retention(moment_of_inertia_gcm2, offset_mm=15.0):
    """Ball speed retained on an off-centre hit: the head twists less when its inertia is higher. A saturating
    curve anchored so that 5900 g cm^2 retains about 0.96 at 15 mm and 2500 retains about 0.90."""
    k = offset_mm / 15.0
    return 1.0 - k * 0.235 * math.exp(-moment_of_inertia_gcm2 / 3200.0) - 0.004 * k


def launch_and_carry(ball_speed_mps, loft_deg, clubhead_speed_mps):
    """Launch angle ~ 0.8 x loft for a driver; carry from a drag-reduced range formula, flat ground, no wind.

    The lift-shape term is re-centred on `peak_loft_deg(clubhead_speed_mps)` rather than a fixed angle, so
    carry peaks at whatever loft suits the swing behind this ball speed, not always near 13 degrees: named
    anchor, about 15% carry loss at 8 degrees off the speed-appropriate peak (0.0024 * 8^2 = 0.1536).
    """
    launch = math.radians(0.8 * loft_deg)
    g = 9.81
    vacuum_range = ball_speed_mps ** 2 * math.sin(2 * launch) / g
    delta_deg = loft_deg - peak_loft_deg(clubhead_speed_mps)
    lift_shape = 1.0 - 2.4e-3 * delta_deg * delta_deg
    flight_factor = 2.04   # re-tuned so a 10-degree driver at the default 45 m/s reference swing carries about 250 m under this toy
    return vacuum_range * lift_shape * flight_factor


def dispersion_proxy(shaft_length_in, moment_of_inertia_gcm2):
    """Longer clubs are harder to square; higher inertia resists twisting. Returned in [0, 1), higher is worse."""
    length_term = (shaft_length_in - 43.0) / 10.0
    inertia_term = 1.0 - moment_of_inertia_gcm2 / 6500.0
    return max(0.0, min(0.99, 0.25 * length_term + 0.35 * inertia_term))


def shell_volume_cc(head_volume_cc, wall_thickness_mm):
    """Thin-shell approximation: sphere-equivalent surface area x wall thickness. Approximate, named; a real
    CAD shell is not this."""
    radius_cm = (3.0 * head_volume_cc / (4.0 * math.pi)) ** (1.0 / 3.0)
    surface_cm2 = 4.0 * math.pi * radius_cm * radius_cm
    return surface_cm2 * (wall_thickness_mm / 10.0)


def min_feasible_head_mass_g(head_volume_cc, density_g_cm3, min_wall_thickness_mm):
    """Thin-shell approximation: sphere-equivalent surface area x wall thickness x density. Approximate,
    named; a real CAD shell is not this. Returns the lightest head this material/thickness can build at
    this volume."""
    return shell_volume_cc(head_volume_cc, min_wall_thickness_mm) * density_g_cm3


def unit_cost_usd(head_volume_cc, head_mass_g, shell_volume_cc, cost_row):
    """material_cost_usd_per_g * head_mass_g + machining_cost_usd_per_cc_removed * (head_volume_cc -
    shell_volume_cc) + fixed_assembly_cost_usd. `cost_row` is one row of the active cost outlet."""
    return (cost_row["material_cost_usd_per_g"] * head_mass_g
            + cost_row["machining_cost_usd_per_cc_removed"] * (head_volume_cc - shell_volume_cc)
            + cost_row["fixed_assembly_cost_usd"])


def lead_time_days(head_volume_cc, shell_volume_cc, production_row):
    """base_lead_time_days + machining_minutes_per_cc * (head_volume_cc - shell_volume_cc) / 1440.0.
    `production_row` is one row of the active production-time outlet."""
    return production_row["base_lead_time_days"] + production_row["machining_minutes_per_cc"] * (head_volume_cc - shell_volume_cc) / 1440.0


# Defaults for the five-objective evaluate() when no outlet row is threaded in (e.g. a bare `evaluate(design)`
# call, as the acceptance harness makes). These mirror the bundled placeholder outlets exactly, so a call with
# no outlet wiring produces the same numbers the placeholder-backed search would.
DEFAULT_MIN_WALL_THICKNESS_MM = 0.6     # legal_club_frontier/data/placeholder_materials.csv
DEFAULT_COST_ROW = {"material_cost_usd_per_g": 0.05, "machining_cost_usd_per_cc_removed": 0.5, "fixed_assembly_cost_usd": 10.0}
DEFAULT_PRODUCTION_ROW = {"base_lead_time_days": 10.0, "machining_minutes_per_cc": 2.0}


def evaluate(design, swing_speed_ref_mps=SWING_SPEED_REF_MPS, min_wall_thickness_mm=None, cost_row=None, production_row=None):
    v_club = clubhead_speed(design["shaft_length_in"], swing_speed_ref_mps)
    cor = coefficient_of_restitution(design["characteristic_time_us"])
    sf = smash_factor(cor, design["head_mass_g"], design["loft_deg"])
    v_ball = v_club * sf
    retention = offcentre_retention(design["moment_of_inertia_gcm2"])
    carry = launch_and_carry(v_ball, design["loft_deg"], v_club)
    wall = DEFAULT_MIN_WALL_THICKNESS_MM if min_wall_thickness_mm is None else min_wall_thickness_mm
    cost_row = DEFAULT_COST_ROW if cost_row is None else cost_row
    production_row = DEFAULT_PRODUCTION_ROW if production_row is None else production_row
    shell_cc = shell_volume_cc(design["head_volume_cc"], wall)
    cost = unit_cost_usd(design["head_volume_cc"], design["head_mass_g"], shell_cc, cost_row)
    lead = lead_time_days(design["head_volume_cc"], shell_cc, production_row)
    return {
        "ball_speed_center_mps": v_ball,
        "forgiveness": retention,
        "carry_proxy_m": carry,
        "unit_cost_usd": cost,
        "lead_time_days": lead,
    }


OBJECTIVES = ("ball_speed_center_mps", "forgiveness", "carry_proxy_m", "unit_cost_usd", "lead_time_days")
OBJECTIVE_DIRECTIONS = {
    "ball_speed_center_mps": "max",
    "forgiveness": "max",
    "carry_proxy_m": "max",
    "unit_cost_usd": "min",
    "lead_time_days": "min",
}
