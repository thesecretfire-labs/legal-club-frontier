"""A deliberately small performance model for a driver, so the search has something to trade off.

THIS IS A TOY. It is here to give the inverse-design search real objectives with real tensions between
them; it is not a validated golf simulator and no number it produces should be quoted as a prediction.
Every relation below is a textbook-shaped approximation, named, so a reader can see exactly what is being
assumed and swap in a better model without touching the search or the rules.

Design fields (all SI except where the rules themselves use inches):
    loft_deg, shaft_length_in, head_volume_cc, head_mass_g, moment_of_inertia_gcm2,
    characteristic_time_us, heel_to_toe_in, face_to_back_in, sole_to_crown_in,
    groove_width_in, groove_depth_in

Objectives returned by `evaluate` (all "higher is better" so the frontier code stays simple):
    ball_speed_center_mps   ball speed on a centred strike
    forgiveness             ball speed retained on a 15 mm off-centre strike, as a fraction of centre
    carry_proxy_m           a carry estimate from speed and launch, flat ground, no wind
    control                 one minus a dispersion proxy that grows with length and falls with inertia
"""
import math

BALL_MASS_G = 45.93           # Rules of Golf, Equipment Rules Part 4: ball mass not greater than 45.93 g
SWING_SPEED_REF_MPS = 45.0    # a strong amateur's clubhead speed with a 45-inch driver, used as the reference
LENGTH_REF_IN = 45.0


def clubhead_speed(shaft_length_in):
    """Clubhead speed scales roughly with the square root of length for the same swing (longer arc, same effort)."""
    return SWING_SPEED_REF_MPS * math.sqrt(shaft_length_in / LENGTH_REF_IN)


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


def launch_and_carry(ball_speed_mps, loft_deg):
    """Launch angle ~ 0.8 x loft for a driver; carry from a drag-reduced range formula, flat ground, no wind."""
    launch = math.radians(0.8 * loft_deg)
    g = 9.81
    vacuum_range = ball_speed_mps ** 2 * math.sin(2 * launch) / g
    s = math.sin(launch)
    lift_shape = 1.0 + 1.6 * s - 16.0 * s * s   # backspin lift helps, then excess spin loft balloons the flight; peaks near 13 degrees of loft
    flight_factor = 1.95                        # empirical scale: a 68 m/s ball at 13 degrees carries about 250 m under this toy
    return vacuum_range * lift_shape * flight_factor


def dispersion_proxy(shaft_length_in, moment_of_inertia_gcm2):
    """Longer clubs are harder to square; higher inertia resists twisting. Returned in [0, 1), higher is worse."""
    length_term = (shaft_length_in - 43.0) / 10.0
    inertia_term = 1.0 - moment_of_inertia_gcm2 / 6500.0
    return max(0.0, min(0.99, 0.25 * length_term + 0.35 * inertia_term))


def evaluate(design):
    v_club = clubhead_speed(design["shaft_length_in"])
    cor = coefficient_of_restitution(design["characteristic_time_us"])
    sf = smash_factor(cor, design["head_mass_g"], design["loft_deg"])
    v_ball = v_club * sf
    retention = offcentre_retention(design["moment_of_inertia_gcm2"])
    carry = launch_and_carry(v_ball, design["loft_deg"])
    control = 1.0 - dispersion_proxy(design["shaft_length_in"], design["moment_of_inertia_gcm2"])
    return {
        "ball_speed_center_mps": v_ball,
        "forgiveness": retention,
        "carry_proxy_m": carry,
        "control": control,
    }


OBJECTIVES = ("ball_speed_center_mps", "forgiveness", "carry_proxy_m", "control")
