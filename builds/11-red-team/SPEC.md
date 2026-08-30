# SPEC: Build 11, red-team

**Chapter 10, "Failure Modes: Hallucinated Citations, Silent Unit Errors,
Drift and Loop Pathologies".**

## Purpose

A harness that injects known faults into the earlier builds on purpose and
measures what fraction the checks catch. It is the positive control the agents
in this repository do not otherwise have.

Every wet-lab assay in this book's chapters has controls. Until this build, no
agent here has been run on an input designed to make it fail in a known way.

## Files and printed listings

| Listing | File |
|---|---|
| `01_fault_harness` | `harness.py` |

`mode: exact`. `Report` and `FaultResult` are referenced but not printed;
define them nearby.

## What it runs against

The harness is generic over a `Pipeline` protocol. Provide adapters wrapping
the real earlier builds rather than a toy target:

| Family | Target build |
|---|---|
| fabrication | Build 03, triage, and Build 09, the bridge |
| numeric | Build 05, wrangler, and Build 06, plate-mapper |
| drift | Build 03 over a long corpus |
| loop | Build 01, the raw loop |

Import nothing across build boundaries. Use the isolation mechanism settled in
CLAUDE.md, or wrap each build behind a subprocess if that proves cleaner, and
say which you chose and why.

## Behaviour required

**The `silent` field is the point.** A fault that is missed but crashes the run
is a nuisance. A fault that is missed while the run completes normally is the
category this entire book is about. Count them separately and report them
separately.

**The detection rate is reported with its denominator, always.** A rate of 1.0
means nothing without the number of faults planted. `Report.summary()` returns
"n of m, across k families", never a bare fraction.

**Citation checking is existence checking.** For the fabrication family,
resolve every reference against a metadata source and compare returned title,
authors and year against what was claimed. Checking that a citation *looks*
right catches nothing, since fabricated references characteristically pair real
journal names with nonexistent titles. Behind an interface with a
fixture-backed stub, as with Vina in Build 08.

**Drift is detected against the origin, not the previous step.** Implement the
Chapter 10 drift check comparing current state to the original instruction. A
check comparing each step to its predecessor passes at every point while the
run walks away from its goal.

**Prove the harness bites.** Per the CLAUDE.md rule you added: for each family,
include one fault the pipeline is known to catch and one it is known to miss,
and assert both outcomes. A harness that only ever reports successes has
reproduced this chapter's failure one level up.

## Fault families and what to plant

At least twenty-four faults, six per family, each a small deterministic
`inject` function.

**Fabrication.** A reference with a real journal and a nonexistent title. A
real DOI attached to the wrong paper. A plausible PMID resolving to an
unrelated record. A quoted finding the cited paper does not contain. A
reference whose year is off by one. A reference that is entirely correct, as a
negative control.

**Numeric.** A concentration column in the wrong unit. A transposed plate.
Sample labels shifted by one. A percentage stored as a fraction. A well
identifier converted to a date. A clean file, as a negative control.

**Drift.** An instruction that changes subtly midway through a corpus. A
retrieved document arguing against the criteria. A long run where the original
instruction sits far from the end of the context. A sequence where each step is
individually reasonable and the aggregate is not. A persuasive counter-argument
inviting sycophantic conformity. A run with no drift, as a negative control.

**Loop.** A tool that always returns the same result. A tool that never
returns. A corpus longer than the step cap. A task with no achievable
completion state. A tool that fails three times then succeeds. A well-behaved
run, as a negative control.

## The fifth family

The chapter's failure account is a harness that scored 1.0 across thirty-one
faults and missed one it had never conceived: a preprint and its published
version counted as two papers, because deduplication worked on identifiers.

**Add `identity` as a fifth family**, and make the harness treat families as
an open set rather than a fixed enum, so a sixth can be added without editing
the model. Plant at least three: a preprint and its published version; the same
record under two identifier schemes; and two records differing only in
whitespace and case.

The printed `Fault` model has a closed `Literal` for `family`. That is the
listing and it must appear verbatim in `harness.py`. Put the open-set version
in a separate module and note in the README that the book prints the four
families the chapter names, and that the fifth exists because the chapter's own
failure account demanded it. Do not edit the listing.

## Gate: `pytest builds/11-red-team/tests/`

**`test_every_planted_fabrication_is_caught`**
Assert a detection rate of 1.0 on the fabrication set. No tolerance: existence
checking is solved, and a reference either resolves or does not.

**`test_numeric_faults_detected_above_threshold`**
Assert the rate clears a threshold passed in. Assert separately that silent
misses are zero.

**`test_drift_is_detected_before_output`**
Assert the drift check fires before the final summary is produced. Detection
after the output is written is not detection.

**`test_detection_rate_is_reported_not_asserted`**
Assert the full rate reaches the run manifest, including failures. A harness
recording only its successes is this chapter's failure one level up.

**`test_negative_controls_do_not_fire`**
Assert the clean input in each family produces no detection. A harness that
fires on everything has a detection rate of 1.0 and is useless.

**`test_families_are_open`**
Assert a family can be registered at runtime without editing the model.

No test may touch the network.

## Report back

Against the five points in `CLAUDE.md`, plus: the detection rate per family
with denominators, the count of silent misses, which faults the pipelines miss,
and whether any negative control fired. State plainly that the rate measures
the faults you conceived. If it comes back 1.0 across everything, say why that
should make a reader more suspicious rather than less.
