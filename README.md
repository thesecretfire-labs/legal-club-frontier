# Legal Club Frontier

Constraints and objectives in, a frontier of legal designs out. A small, runnable example of inverse design, built so a stranger can read the whole thing in ten minutes and run it in two.

Think of the rules and the physics as a surge protector built into the wall: fixed, not something you plug things into. The things you plug in -- a material data set, a cost data set, a production-time data set, a machining-accuracy data set -- are the outlets. You bring the data; the strip takes care of knowing what's legal and what the physics trades off, same as before.

The example is a golf driver, because the constraint set is public and fully written down: the equipment rules of golf say exactly how big a clubhead may be, how long a shaft may be, how springy a face may be. The search samples a design space deliberately **wider** than those rules, keeps what is legal, scores each legal design on five objectives that pull against each other, and returns the Pareto frontier: the designs you cannot improve on one objective without giving something up on another.

The golf is the example. The shape is the point, and the shape is generic:

1. **A constraint table with a citation on every number** (`legal_club_frontier/rules.py`). The limits are stored once, as data, each beside the rule it comes from and the date it was last checked against the published text.
2. **A legality predicate** that reads that table and says, for any design, legal or not, and why not.
3. **An objective function** (`model.py`) that is deliberately small and names every assumption it makes.
4. **A non-dominated sort** (`search.py`) over a seeded sample plus a few rounds of local refinement.
5. **A run record** that names the seed, the rule-table fingerprint, the model's hash, and the counts, and is marked `NOT REVIEWED` by the program itself, because a program does not get to accept its own output.
6. **An acceptance harness** (`tests/`) with three inputs broken on purpose that must be refused, a check that this README's quoted limits match the code byte for byte, and a mutation proof that swaps in an approve-everything predicate and demands the harness fail.

Swap the rules file and the model and nothing else changes. That is what inverse design looks like when the constraints are first-class.

## Run it

```
pip install numpy
python -m legal_club_frontier
```

About seven seconds. You get a table of the top frontier designs and a run record under `runs/`.

```
python -m unittest tests.test_acceptance_harness -v        # the twenty-one checks
python -m tests.test_acceptance_harness --mutation-proof   # prove the harness would notice a liar
```

## What the rules say

The limits the search enforces, as transcribed from the USGA / R&A Equipment Rules, Part 2 (Clubs), 2019 numbering. A test compares every number in this table to the constant in `rules.py`; if they ever disagree, the test fails and names the line.

<!-- rules-table-start -->
| field | limit | unit | rule |
|---|---|---|---|
| `shaft_length_in` | 48 | inch, maximum | Part 2, Rule 1c (Length) |
| `shaft_length_in_min` | 18 | inch, minimum | Part 2, Rule 1c (Length) |
| `head_volume_cc` | 460 | cubic centimetre, maximum (+10 tolerance) | Part 2, Rule 4b(i) (Size) |
| `heel_to_toe_in` | 5 | inch, maximum | Part 2, Rule 4b(i) (Dimensions) |
| `sole_to_crown_in` | 2.8 | inch, maximum | Part 2, Rule 4b(i) (Dimensions) |
| `moment_of_inertia_gcm2` | 5900 | gram centimetre squared, maximum (+100 tolerance) | Part 2, Rule 4b(ii) (Moment of Inertia) |
| `characteristic_time_us` | 239 | microsecond, maximum (+18 tolerance) | Part 2, Rule 4c (Spring Effect) |
| `groove_width_in` | 0.035 | inch, maximum | Part 2, Rule 5c (Grooves) |
| `groove_depth_in` | 0.02 | inch, maximum | Part 2, Rule 5c (Grooves) |
| `groove_separation_in_min` | 0.075 | inch, minimum | Part 2, Rule 5c (Grooves) |
<!-- rules-table-end -->

Plus two relations between fields: the face-to-back distance may not exceed the heel-to-toe distance (Part 2, Rule 4b(i)), and the distance between adjacent grooves may not be less than three times the groove width (Part 2, Rule 5c).

One optional rule is a note, not a limit: Model Local Rule G-10 (2022) lets a committee cap overall length at 46 inches for its competition. The base 48-inch rule stands; a designer aiming at elite competition should bound the shaft search at 46.

**Which rulebook, and from where.** The USGA / R&A Equipment Rules, Part 2 (Clubs), using the 2019 edition's rule numbering, read from the USGA's own pages (`rules.SOURCES` lists the three URLs: Part 2 Rules 1, 4 and 5). The numbers were transcribed by a person and cross-checked on the date in `rules.verify_date`, not pulled from an API; a later edition (v1.3, December 2024) exists and its section numbering was not re-verified. Equipment rules change, and it does not matter to the shape of this program which edition is loaded: what matters is that the edition is named, the table is fingerprinted into every run record, and the program refuses a design the named rules refuse. If a limit no longer matches the current text, the fix is one line in `rules.py`, and the README test will tell you which quotation to update.

## What the model is, and is not

`model.py` is a toy. It exists so the search has real tensions to trade off: a longer shaft swings faster but is harder to square; a springier face adds ball speed up to the legal limit; more moment of inertia forgives an off-centre strike; more loft launches higher until the flight balloons, and the loft that carries farthest falls as swing speed rises. Every relation is a textbook-shaped approximation with its anchors named in the source. No number it produces is a prediction about a real club, and the README will not quote one.

The honest reading of a frontier from this model is: *given these assumptions and these outlets, these are the legal, feasible designs that are not dominated by any other legal, feasible design.* Change an assumption, or swap an outlet, and the frontier moves. That is a feature; the record tells you which model hash and which outlets produced which frontier.

The placeholder material, cost, production-time, and machining-accuracy numbers are invented for wiring and testing only. They are not real material properties, real prices, real lead times, or a real shop's real tolerance. Swapping them for honest numbers is the entire point of the outlets; the program does not grade whether the numbers you bring are honest.

**What this does NOT claim:**

- Does not predict a real club's performance.
- Does not know any real material, price, lead time, or shop's actual tolerance.
- The carry model is a named toy, not a launch-monitor fit.
- The cost and lead-time formulas are a shell-volume proxy, not a CAD model or a quote.

## Bring your own data

The rules and the physics core are the fixed strip. Four small CSV-backed datasets are the outlets you plug into it, each with one fixed header (the contract), loaded by `legal_club_frontier/outlets.py`. Ships with a bundled placeholder for each, every row labelled `PLACEHOLDER - NOT REAL DATA, FOR WIRING AND TESTING ONLY`; pass `--materials-csv`, `--cost-csv`, `--production-time-csv`, or `--machining-accuracy-csv` to replace one, and the run still works when you leave the rest on the placeholder.

<!-- outlets-table-start -->
| outlet | header |
|---|---|
| `materials` | `material_id,display_name,density_g_cm3,min_wall_thickness_mm,source_note,is_placeholder_data` |
| `cost` | `material_id,material_cost_usd_per_g,machining_cost_usd_per_cc_removed,fixed_assembly_cost_usd,source_note,is_placeholder_data` |
| `production_time` | `material_id,base_lead_time_days,machining_minutes_per_cc,source_note,is_placeholder_data` |
| `machining_accuracy` | `shop_id,shop_name,field_name,shop_tolerance,unit,source_note,is_placeholder_data` |
<!-- outlets-table-end -->

- **Materials.** Ships with `legal_club_frontier/data/placeholder_materials.csv`, labelled `PLACEHOLDER - NOT REAL DATA, FOR WIRING AND TESTING ONLY` in every row; pass `--materials-csv yourfile.csv` to replace it. Feeds `model.min_feasible_head_mass_g`: a design whose head is lighter than this material/thickness can build at that volume is rejected as infeasible, separately from the legality filter.
- **Cost.** Ships with `legal_club_frontier/data/placeholder_cost.csv`, labelled `PLACEHOLDER - NOT REAL DATA, FOR WIRING AND TESTING ONLY` in every row; pass `--cost-csv yourfile.csv` to replace it. Feeds the `unit_cost_usd` objective (lower is better).
- **Production time.** Ships with `legal_club_frontier/data/placeholder_production_time.csv`, labelled `PLACEHOLDER - NOT REAL DATA, FOR WIRING AND TESTING ONLY` in every row; pass `--production-time-csv yourfile.csv` to replace it. Feeds the `lead_time_days` objective (lower is better).
- **Machining accuracy.** Ships with `legal_club_frontier/data/placeholder_machining_accuracy.csv`, labelled `PLACEHOLDER - NOT REAL DATA, FOR WIRING AND TESTING ONLY` in every row; pass `--machining-accuracy-csv yourfile.csv` to replace it. Long format, one row per (shop, ruled field); tightens the legality bound that field is judged against (the "±5 cc shop" case) and is reported as a legality margin on every frontier entry, never optimized.

The materials, cost, and production-time outlets are "one profile per file": the first data row is the active profile, so comparing two profiles means running the program twice with two files. The machining-accuracy outlet collects every row whose `shop_id` matches the first `shop_id` seen; a file naming more than one shop is a user error to split into separate files, not something the loader guesses at.

## Two driver scenarios

`--loft 8.5` and `--loft 10` (or `10.0`) fix loft and print one table each; omit `--loft` and the program runs both, printing two tables and writing two run records. `--swing-speed-mps` (default 45.0) is the reference clubhead speed behind that: the model's carry term peaks near a loft that falls as swing speed rises, so a fixed-loft comparison is only legible once the swing speed behind it is named. A slow swing shows the 10-degree table carrying farther; a fast swing shows the 8.5-degree table carrying farther, because the peak has moved toward it.

## What the harness is for

Most pipelines treat "the command exited 0" and "the result is right" as one fact. They are two. The harness keeps them apart:

- **Negative controls.** Three designs are illegal on purpose: a 470 cc head, a 49-inch shaft, a 300-microsecond face. The same predicate that passes legal designs must refuse each of these. A harness that has only ever seen good input cannot tell you it works.
- **Drift against source.** The rules table and the outlets table above are each checked against the code byte for byte. A paraphrase that drifts goes red.
- **The record cites its evidence.** Every run record carries the fingerprint of the rule table it was judged by, the hash of the model, which outlets were placeholders, and which shop tolerances were applied. A frontier without that is a picture, not a result.
- **Mutation proof.** `--mutation-proof` replaces the legality predicate with one that approves everything, and separately a mutant that zeroes out every shop tolerance, then re-runs the harness. The harness must fail on both, and the output names which checks caught each mutant. A test suite that still passes with a liar wired in was never testing anything.

## Author

Aaron Brown, 2026. Written from scratch for this repository; numpy and the standard library only. MIT licence.
