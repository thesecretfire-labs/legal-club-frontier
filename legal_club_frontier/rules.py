"""The constraint set: the equipment limits a driver must satisfy to be legal under the Rules of Golf.

Every limit below is a number taken from the USGA / R&A Equipment Rules (Part 2, "Clubs"), with the rule it
comes from named beside it. The limits are stored ONCE, here, as data; the README quotes them, and a test
checks that the README's quotations match these constants byte for byte, so a paraphrase can never drift
from the source without a test going red.

Read before relying on any of this: these numbers were transcribed from the published rules by a person,
not pulled from an API, and equipment rules change. `verify_date` records when they were last checked. If
you find a limit that no longer matches the current text, the fix is one line here and the tests will tell
you which quotation in the README to update.

Units are stated on every field. Nothing here models whether a club is GOOD; this file only says whether a
club is ALLOWED.
"""
from dataclasses import dataclass, asdict
import hashlib
import json


@dataclass(frozen=True)
class Limit:
    name: str
    value: float
    unit: str
    kind: str          # "max" or "min"
    rule: str          # where in the Equipment Rules the number comes from
    tolerance: float = 0.0   # the manufacturing tolerance the rules allow on top of the limit, same unit


# Part 2 of the Equipment Rules, "Clubs". Rule numbers follow the 2019 edition's numbering.
LIMITS = (
    Limit("shaft_length_in", 48.0, "inch", "max", "Part 2, Rule 1c (Length): overall length must not exceed 48 inches, putters excepted"),
    Limit("shaft_length_in_min", 18.0, "inch", "min", "Part 2, Rule 1c (Length): overall length must be at least 18 inches"),
    Limit("head_volume_cc", 460.0, "cubic centimetre", "max", "Part 2, Rule 4b(i) (Size): clubhead volume must not exceed 460 cc", tolerance=10.0),
    Limit("heel_to_toe_in", 5.0, "inch", "max", "Part 2, Rule 4b(i) (Dimensions): distance from heel to toe must not exceed 5 inches"),
    Limit("sole_to_crown_in", 2.8, "inch", "max", "Part 2, Rule 4b(i) (Dimensions): distance from sole to crown must not exceed 2.8 inches"),
    Limit("moment_of_inertia_gcm2", 5900.0, "gram centimetre squared", "max", "Part 2, Rule 4b(ii) (Moment of Inertia): must not exceed 5900 g cm^2", tolerance=100.0),
    Limit("characteristic_time_us", 239.0, "microsecond", "max", "Part 2, Rule 4c (Spring Effect): characteristic time must not exceed 239 microseconds", tolerance=18.0),
    Limit("groove_width_in", 0.035, "inch", "max", "Part 2, Rule 5c (Grooves): groove width must not exceed 0.035 inch"),
    Limit("groove_depth_in", 0.020, "inch", "max", "Part 2, Rule 5c (Grooves): groove depth must not exceed 0.020 inch"),
)

# The face-to-back dimension may not exceed the heel-to-toe dimension (Part 2, Rule 4b(i)); it is a relation
# between two fields, not a single number, so it is checked in code below rather than listed as a Limit.
FACE_TO_BACK_RULE = "Part 2, Rule 4b(i) (Dimensions): distance from face to back must not exceed distance from heel to toe"

verify_date = "2026-10-06"   # the day these limits were last read against the published text


def limits_by_name():
    return {l.name: l for l in LIMITS}


def rules_fingerprint():
    """A hash of the whole constraint table, so every run record can say exactly which rules it was judged by."""
    blob = json.dumps([asdict(l) for l in LIMITS] + [FACE_TO_BACK_RULE, verify_date], sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def legality(design, *, allow_tolerance=False):
    """Return (legal, reasons). `design` is a dict of the fields named in LIMITS plus face_to_back_in.

    `allow_tolerance=False` judges against the bare limit, the conservative reading a designer should use;
    `allow_tolerance=True` adds the rules' stated manufacturing tolerance, the reading a conformance test
    would apply to a finished club. Both are reported in the run record so nobody has to guess which was used.
    """
    reasons = []
    for l in LIMITS:
        v = design[l.name.replace("_min", "")] if l.name.endswith("_min") else design[l.name]
        bound = l.value + (l.tolerance if (allow_tolerance and l.kind == "max") else 0.0)
        if l.kind == "max" and v > bound:
            reasons.append(f"{l.name} = {v:g} {l.unit} exceeds {bound:g} ({l.rule})")
        if l.kind == "min" and v < l.value:
            reasons.append(f"{l.name} = {v:g} {l.unit} is below {l.value:g} ({l.rule})")
    if design["face_to_back_in"] > design["heel_to_toe_in"]:
        reasons.append(f"face_to_back_in = {design['face_to_back_in']:g} exceeds heel_to_toe_in = {design['heel_to_toe_in']:g} ({FACE_TO_BACK_RULE})")
    return (not reasons), reasons
