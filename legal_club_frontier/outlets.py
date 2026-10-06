"""The outlets: small CSV-backed datasets you plug into the fixed strip (rules.py + the physics core of
model.py). Four contracts, each a fixed header, each with a bundled placeholder file so the search always
runs even when you bring nothing of your own.

Every outlet CSV carries two trailing columns shared across all four files: `source_note` (placeholder rows
hold exactly `PLACEHOLDER_LABEL`) and `is_placeholder_data` (`TRUE`/`FALSE`). `load_outlet` reads that column
to decide `meta["is_placeholder"]` rather than sniffing the filename, even though the filename says so too.

Degradation rule: an *omitted* path loads the bundled placeholder and the run still works. A path that is
given but wrong (missing, unreadable, wrong header) is refused loudly with `OutletError`, never silently
swapped for the placeholder.
"""
import csv
import hashlib
import pathlib
from dataclasses import dataclass

DATA_DIR = pathlib.Path(__file__).resolve().parent / "data"

PLACEHOLDER_LABEL = "PLACEHOLDER - NOT REAL DATA, FOR WIRING AND TESTING ONLY"


class OutletError(Exception):
    """Raised when an outlet CSV is missing, unreadable, has the wrong header, or mixes placeholder flags."""


@dataclass(frozen=True)
class OutletSpec:
    name: str                 # "materials" | "cost" | "production_time" | "machining_accuracy"
    header: tuple            # exact column order the CSV must carry
    placeholder_path: pathlib.Path


MATERIALS = OutletSpec(
    "materials",
    ("material_id", "display_name", "density_g_cm3", "min_wall_thickness_mm", "source_note", "is_placeholder_data"),
    DATA_DIR / "placeholder_materials.csv",
)
COST = OutletSpec(
    "cost",
    ("material_id", "material_cost_usd_per_g", "machining_cost_usd_per_cc_removed", "fixed_assembly_cost_usd",
     "source_note", "is_placeholder_data"),
    DATA_DIR / "placeholder_cost.csv",
)
PRODUCTION_TIME = OutletSpec(
    "production_time",
    ("material_id", "base_lead_time_days", "machining_minutes_per_cc", "source_note", "is_placeholder_data"),
    DATA_DIR / "placeholder_production_time.csv",
)
MACHINING_ACCURACY = OutletSpec(
    "machining_accuracy",
    ("shop_id", "shop_name", "field_name", "shop_tolerance", "unit", "source_note", "is_placeholder_data"),
    DATA_DIR / "placeholder_machining_accuracy.csv",
)
OUTLETS = (MATERIALS, COST, PRODUCTION_TIME, MACHINING_ACCURACY)


def _fingerprint(rows):
    blob = repr(rows).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def load_outlet(spec, path=None):
    """Returns (rows, meta). meta = {outlet, source_path, is_placeholder, row_count, fingerprint}.

    path=None -> loads spec.placeholder_path (the search still runs; meta['is_placeholder'] = True).
    path given but missing/unreadable -> OutletError naming the path (loud, never a silent fallback).
    header mismatch -> OutletError naming the missing/unexpected columns against spec.header.
    is_placeholder_data column must be uniformly TRUE, uniformly FALSE, or a mix -> OutletError if mixed.
    """
    used_placeholder = path is None
    p = spec.placeholder_path if used_placeholder else pathlib.Path(path)

    if not used_placeholder and not p.exists():
        raise OutletError(f"outlet '{spec.name}': path does not exist: {path}")

    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise OutletError(f"outlet '{spec.name}': could not read {p}: {exc}") from exc

    reader = csv.DictReader(text.splitlines())
    fieldnames = tuple(reader.fieldnames or ())
    if fieldnames != spec.header:
        missing = [c for c in spec.header if c not in fieldnames]
        unexpected = [c for c in fieldnames if c not in spec.header]
        raise OutletError(
            f"outlet '{spec.name}': header at {p} does not match the contract. "
            f"missing={missing} unexpected={unexpected} expected_order={list(spec.header)}"
        )
    rows = list(reader)

    flags = {row["is_placeholder_data"].strip().upper() for row in rows}
    if flags - {"TRUE", "FALSE"}:
        raise OutletError(f"outlet '{spec.name}': is_placeholder_data at {p} has values other than TRUE/FALSE: {flags}")
    is_placeholder = used_placeholder or (flags == {"TRUE"})

    meta = {
        "outlet": spec.name,
        "source_path": str(p),
        "is_placeholder": is_placeholder,
        "row_count": len(rows),
        "fingerprint": _fingerprint(rows),
    }
    return rows, meta


def load_all_outlets(materials_path=None, cost_path=None, production_time_path=None, machining_accuracy_path=None):
    """Returns (data_by_outlet, meta_by_outlet, placeholder_outlet_names)."""
    data_by_outlet = {}
    meta_by_outlet = {}
    placeholder_outlet_names = []
    for spec, path in (
        (MATERIALS, materials_path),
        (COST, cost_path),
        (PRODUCTION_TIME, production_time_path),
        (MACHINING_ACCURACY, machining_accuracy_path),
    ):
        rows, meta = load_outlet(spec, path=path)
        data_by_outlet[spec.name] = rows
        meta_by_outlet[spec.name] = meta
        if meta["is_placeholder"]:
            placeholder_outlet_names.append(spec.name)
    return data_by_outlet, meta_by_outlet, placeholder_outlet_names
