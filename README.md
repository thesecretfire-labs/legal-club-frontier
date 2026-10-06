# Legal Club Frontier

Constraints and objectives in, a frontier of legal designs out. A small, runnable example of inverse design, built so a stranger can read the whole thing in ten minutes and run it in two.

The example is a golf driver, because the constraint set is public and fully written down: the equipment rules of golf say exactly how big a clubhead may be, how long a shaft may be, how springy a face may be. The search samples a design space deliberately **wider** than those rules, keeps what is legal, scores each legal design on four objectives that pull against each other, and returns the Pareto frontier: the designs you cannot improve on one objective without giving something up on another.

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
python -m unittest tests.test_acceptance_harness -v        # the thirteen checks
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
<!-- rules-table-end -->

Plus one relation between two fields: the face-to-back distance may not exceed the heel-to-toe distance (Part 2, Rule 4b(i)).

These numbers were transcribed by a person on the date in `rules.verify_date`, not pulled from an API. Equipment rules change. If one no longer matches the current text, the fix is one line in `rules.py`, and the README test will tell you which quotation to update.

## What the model is, and is not

`model.py` is a toy. It exists so the search has real tensions to trade off: a longer shaft swings faster but is harder to square; a springier face adds ball speed up to the legal limit; more moment of inertia forgives an off-centre strike; more loft launches higher until the flight balloons. Every relation is a textbook-shaped approximation with its anchors named in the source. No number it produces is a prediction about a real club, and the README will not quote one.

The honest reading of a frontier from this model is: *given these assumptions, these are the legal designs that are not dominated by any other legal design.* Change an assumption and the frontier moves. That is a feature; the record tells you which model hash produced which frontier.

## What the harness is for

Most pipelines treat "the command exited 0" and "the result is right" as one fact. They are two. The harness keeps them apart:

- **Negative controls.** Three designs are illegal on purpose: a 470 cc head, a 49-inch shaft, a 300-microsecond face. The same predicate that passes legal designs must refuse each of these. A harness that has only ever seen good input cannot tell you it works.
- **Drift against source.** The table above is checked against `rules.py` byte for byte. A paraphrase that drifts goes red.
- **The record cites its evidence.** Every run record carries the fingerprint of the rule table it was judged by and the hash of the model. A frontier without those two numbers is a picture, not a result.
- **Mutation proof.** `--mutation-proof` replaces the legality predicate with one that approves everything and re-runs the harness. The harness must fail, and the output names which checks caught the mutant. A test suite that still passes with an approve-everything predicate was never testing anything.

## Author

Aaron Brown, 2026. Written from scratch for this repository; numpy and the standard library only. MIT licence.
