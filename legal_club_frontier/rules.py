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
    Limit("groove_separation_in_min", 0.075, "inch", "min", "Part 2, Rule 5c (Grooves): the distance between adjacent grooves must not be less than 0.075 inch"),
)

# Two rules are relations between fields, not single numbers, so they are checked in code below rather than
# listed as a Limit: the face-to-back dimension may not exceed heel-to-toe (Rule 4b(i)), and groove separation
# may not be less than three times groove width (Rule 5c).
FACE_TO_BACK_RULE = "Part 2, Rule 4b(i) (Dimensions): distance from face to back must not exceed distance from heel to toe"
GROOVE_SPACING_RULE = "Part 2, Rule 5c (Grooves): the distance between adjacent grooves must not be less than three times the groove width"

# A committee may adopt Model Local Rule G-10 (introduced 2022) capping overall length at 46 inches for its
# competition. It is optional and does not change Rule 1c's 48-inch limit, so it is a note here, not a Limit;
# a designer aiming at elite competition should search with shaft_length_in bounded at 46.
COMPETITION_LENGTH_NOTE = "Model Local Rule G-10 (2022): a committee may limit overall length to 46 inches (0.20 inch tolerance), putters excepted"

# Where the numbers come from, so a run is reproducible against a named text. "Equipment Rules" means the
# USGA / R&A Rules of Golf Equipment Rules; the rule numbering used throughout is the 2019 edition's, which the
# USGA publishes at usga.org/equipment-standards/equipment-rules-2019/ (Part 2 pages: rule-1, rule-4, rule-5).
# The numbers were read from those pages and cross-checked on 2026-10-06 against search-indexed copies of the
# same pages; the primary pages themselves could not be fetched by machine that day, so this is a human
# reading of a public text, dated, not an automated feed. A later edition (v1.3, December 2024) exists; its
# section numbering was not re-verified. If any limit no longer matches the current text, change it here.
EDITION = "USGA / R&A Equipment Rules, Part 2 (Clubs), 2019 edition numbering"
SOURCES = (
    "https://www.usga.org/equipment-standards/equipment-rules-2019/equipment-rules/part-2-rule-1.html",
    "https://www.usga.org/equipment-standards/equipment-rules-2019/equipment-rules/part-2-rule-4.html",
    "https://www.usga.org/equipment-standards/equipment-rules-2019/equipment-rules/part-2-rule-5.html",
)

verify_date = "2026-10-06"   # the day these limits were last read against the published text


def limits_by_name():
    return {l.name: l for l in LIMITS}


def rules_fingerprint():
    """A hash of the whole constraint table, so every run record can say exactly which rules it was judged by."""
    blob = json.dumps([asdict(l) for l in LIMITS] + [FACE_TO_BACK_RULE, GROOVE_SPACING_RULE, EDITION, *SOURCES, verify_date], sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _effective_bound(l, allow_tolerance, shop_tolerances):
    """The bound `legality`/`legality_margins` actually judges against, after the rules' own tolerance
    (only on `allow_tolerance=True`) and a shop's machining tolerance (always, if named) are applied.

    For a 'max' field: bound = l.value + (l.tolerance if allow_tolerance else 0) - shop_tolerances.get(l.name, 0).
    For a 'min' field: bound = l.value + shop_tolerances.get(l.name, 0).
    """
    shop = shop_tolerances.get(l.name, 0.0) if shop_tolerances else 0.0
    if l.kind == "max":
        return l.value + (l.tolerance if allow_tolerance else 0.0) - shop
    return l.value + shop


def legality(design, *, allow_tolerance=False, shop_tolerances=None):
    """Return (legal, reasons). `design` is a dict of the fields named in LIMITS plus face_to_back_in.

    `allow_tolerance=False` judges against the bare limit, the conservative reading a designer should use;
    `allow_tolerance=True` adds the rules' stated manufacturing tolerance, the reading a conformance test
    would apply to a finished club. Both are reported in the run record so nobody has to guess which was used.

    `shop_tolerances`: dict[field_name -> tolerance in the field's native unit], default {} (no tightening).
    A shop's own machining tolerance tightens the bound a design must clear before it reaches the shop floor:
    for a 'max' field, effective bound = l.value + (l.tolerance if allow_tolerance else 0) - shop_tolerances.get(l.name, 0);
    for a 'min' field, effective bound = l.value + shop_tolerances.get(l.name, 0).
    """
    reasons = []
    for l in LIMITS:
        v = design[l.name.replace("_min", "")] if l.name.endswith("_min") else design[l.name]
        bound = _effective_bound(l, allow_tolerance, shop_tolerances)
        if l.kind == "max" and v > bound:
            reasons.append(f"{l.name} = {v:g} {l.unit} exceeds {bound:g} ({l.rule})")
        if l.kind == "min" and v < bound:
            reasons.append(f"{l.name} = {v:g} {l.unit} is below {bound:g} ({l.rule})")
    if design["face_to_back_in"] > design["heel_to_toe_in"]:
        reasons.append(f"face_to_back_in = {design['face_to_back_in']:g} exceeds heel_to_toe_in = {design['heel_to_toe_in']:g} ({FACE_TO_BACK_RULE})")
    if design["groove_separation_in"] < 3.0 * design["groove_width_in"]:
        reasons.append(f"groove_separation_in = {design['groove_separation_in']:g} is less than three times groove_width_in = {design['groove_width_in']:g} ({GROOVE_SPACING_RULE})")
    return (not reasons), reasons


def legality_margins(design, *, allow_tolerance=False, shop_tolerances=None):
    """Per ruled field, (effective_bound - value) for max fields, (value - effective_bound) for min fields.

    Negative means illegal on that field; this is the number the owner calls the legality margin.
    """
    margins = {}
    for l in LIMITS:
        v = design[l.name.replace("_min", "")] if l.name.endswith("_min") else design[l.name]
        bound = _effective_bound(l, allow_tolerance, shop_tolerances)
        margins[l.name] = (bound - v) if l.kind == "max" else (v - bound)
    return margins
