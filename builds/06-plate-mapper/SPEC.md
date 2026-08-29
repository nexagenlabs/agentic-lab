# SPEC: Build 06, plate-mapper

**Chapter 6, "Protocol Agents: Drafting, Adapting and Sanity-Checking Wet-Lab
Procedures".**

## Purpose

Lay out a combination matrix, check the dilution arithmetic before anything is
pipetted, and force a commitment to a synergy model before any data exists.

The chapter opens with an admission: the author ran the matrices, then chose
the synergy model after seeing the surfaces. Four candidate models plus a
post-hoc choice is four chances at a positive number. This build makes that
impossible, and the mechanism is a timestamp.

## Files and printed listings

| Listing | File |
|---|---|
| `01_design_file` | `designs/tmz_na_u87mg.yaml` |
| `02_dilution_check` | `checks.py` |

Both `mode: exact`. `EXPECTED_IC50` and `MIN_RELIABLE_UL` are referenced but
not printed; define them as module constants with a comment saying where the
values come from.

## Behaviour required

**The design is a declaration and it comes first.** Everything is in the YAML:
cell line with an RRID, seeding density, plate format, both dose axes with top
concentration, dilution factor and step count, controls, edge policy,
replicates, randomisation, and the analysis block.

**The RRID is not optional.** The design carries `rrid: CVCL_0022`, not just
`U87MG`. Chapter 6 reports a commercial authentication service finding 4.7 per
cent of submitted lines misidentified in 2024 and 2.4 per cent in 2025. A name
is a label and labels have been wrong. Validation rejects a design with a cell
line name and no RRID.

**The synergy commitment is timestamped and checked against the data.** The
`analysis` block names a model, gives a mechanistic justification in prose, and
carries `committed_at`. Implement `check_commitment_precedes_data(design_path,
results_dir)` which compares the commit timestamp against the earliest reading
in the results directory and fails if the model was chosen after data existed.

Some readers will find comparing a file timestamp to a data timestamp
excessive. Put the reason in the docstring: a model chosen after the fact
leaves no trace in the analysis, the figures or the manuscript, so the
timestamp is the only surviving evidence.

**The agent proposes the layout; code checks it.** Same division as Build 05.
`check_dilution_series` is pure Python and calls no model.

**Model selection is refused.** `choose_synergy_model()` must raise. The model
encodes a mechanistic claim about how two agents interact, and that claim
belongs to a person who can defend it. The agent's job is to record the claim,
check the plate can support it, and refuse to proceed if it has not been made.
The error message should say so.

**Bliss and ZIP are not independent evidence.** If a design requests a
consensus across models, reject a set containing both, with a message noting
that SynergyFinder excludes ZIP from its consensus for exactly this reason.
This is the trap most readers will not know.

**Layout.** Perimeter wells filled with buffer and excluded when
`edge_policy: exclude_perimeter`. Controls on every plate, not a reference
plate. Treatment positions randomised within the plate with the seed recorded
in the design, so the wrangler from Build 05 can verify returning data against
the layout. A layout you cannot reproduce is one nothing can check.

## Fixtures

- `designs/tmz_na_u87mg.yaml`, the printed design, verbatim.
- `fixtures/bad_designs/`, seven designs each failing one validation, each with
  a `.expected.json` naming the failure: no RRID; solvent above tolerance at
  top dose; transfer volume below the pipetting minimum; a series that never
  drops below the expected IC50; wells that do not balance against the format;
  no synergy model committed; `committed_at` later than the earliest result.
- `fixtures/results/`, a small set of dated readings for the commitment test.

## Gate: `pytest builds/06-plate-mapper/tests/`

**`test_dilution_series_is_physical`**
Assert every transfer volume clears the pipetting minimum, solvent percentage
at top dose is within tolerance, and the series spans the expected IC50 with at
least one point each side. A series with no lower plateau makes the fitted
IC50 an extrapolation, and the reader will not find out until the cells are
gone.

**`test_well_count_balances`**
Assert treatment plus controls plus excluded perimeter equals the plate format
exactly.

**`test_synergy_model_committed_before_data`**
Assert the design names a model with a written justification, and that
`committed_at` precedes the earliest reading. This test is the whole point of
the chapter.

**`test_rrid_is_required`**
Assert a design with a cell line name and no RRID is rejected.

**`test_model_selection_is_refused`**
Assert `choose_synergy_model()` raises, and that the message explains why.

**`test_bliss_and_zip_not_both_in_consensus`**
Assert a consensus request containing both is rejected.

**`test_layout_is_reproducible`**
Generate the layout twice from the same seed; assert identical well
assignments. Then with a different seed; assert they differ.

**`test_bad_designs_are_rejected`**
Run all seven bad designs; assert each is rejected with the failure named in
its `.expected.json`.

No test may touch the network.

## Out of scope

Protocol adaptation is Build 07, whose listing exists in the manifest and whose
target is `builds/07-protocol-adapter/models.py`. Do not start it.

## Report back

Against the five points in `CLAUDE.md`, plus whether any of the seven bad
designs passed when it should not, and whether the printed dilution check
catches all three problems it claims to on the printed design.
