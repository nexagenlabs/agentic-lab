# Build 11: Red Team

Introduced in **Chapter 10** of *The Agentic Lab*, "Failure Modes: Hallucinated
Citations, Silent Unit Errors, Drift and Loop Pathologies".

A harness that injects known faults into the earlier builds on purpose and
measures what fraction the checks catch. It is the positive control the agents
in this repository did not otherwise have.

Every wet-lab assay in this book has controls. Until this build, no agent here
had been run on an input designed to make it fail in a known way, which means
no claim about any of them had a denominator.

## The result

Thirty-one faults planted across five families, of which twenty-five are faults
and six are negative controls. Negative controls are never counted in the
denominator: a clean input is not a fault, and putting one in the numerator is
the cheapest way to make a detection rate look better than it is.

| Family | Planted | Earlier builds alone | With this build's checks |
|---|---|---|---|
| fabrication | 5 | **0** | 5 |
| numeric | 6 | 5 | 6 |
| drift | 5 | 1 | 5 |
| loop | 5 | 4 | 5 |
| identity | 4 | 1 | 4 |
| **total** | **25** | **11 of 25** | **25 of 25** |

Six negative controls, none of which fired anything.

**Every one of the fourteen faults the earlier builds miss is a silent miss.**
Not one of them crashed. In all fourteen the run completed, returned an answer,
wrote a clean trace and said nothing was wrong. That is the number this build
exists to produce, and it is the category the whole book is about.

## The rate is 1.0 with the checks attached, and that should worry you

Twenty-five of twenty-five. The chapter's failure account is a harness that
scored exactly this and was wrong, so it is worth being explicit about what the
number does and does not mean.

**It measures the faults I conceived of.** I wrote the faults and I wrote the
checks, in that order, in the same afternoon. A check written to catch a fault
catches it. The rate is a statement about the agreement between two things one
person produced, and treating it as a statement about the system is the mistake
Chapter 10 is about.

**The interesting column is the other one.** Eleven of twenty-five is what the
repository actually did before this build existed, and that number was produced
by code written weeks earlier for other reasons. It is the only figure here
that was not chosen.

**The fifth family is the evidence.** `identity` exists because the chapter's
harness scored 1.0 across thirty-one faults and missed a preprint counted
twice. It was not a bad check. Deduplication worked on identifiers, correctly,
and a preprint and its published version have different identifiers, correctly.
There was no check because there was no family, and the list of families was a
list somebody finished writing one afternoon. Adding `identity` moved the bare
detection rate for that family from an unmeasured 1.0 to a measured 1 of 4.

So the honest reading of 25 of 25 is: go and find the sixth family. That is
what `families.py` is for.

## The `silent` field is the point

A fault that is missed but crashes the run is a nuisance. Somebody sees a
traceback and looks. A fault that is missed while the run completes normally,
returns a plausible answer and writes a clean manifest is the thing this book
is about, and the two are counted and reported separately everywhere in the
build.

`Report` has `rate()` returning a pair, `summary()` returning "n of m, across k
families; s silent", and no method anywhere that returns a bare float. A single
number in a manifest is what gets copied onto a slide, and by the time it is on
the slide nobody can ask what the denominator was.

## What each family found

**Fabrication: 0 of 5 unaided.** Neither Build 03 nor Build 09 has any citation
check at all, so all five went through silently. `citations.py` supplies the
missing one, and it is existence checking rather than plausibility checking:
resolve the identifier, then compare the returned title, authors and year
against what was claimed. Checking that a citation *looks* right catches
nothing, because looking right is what a fabricated reference is good at. The
third check is the one people leave out: `citation_quote_supported`, where the
identifier resolves, the metadata agrees, and the sentence attributed to the
paper is not in it.

**Numeric: 5 of 6 unaided.** Build 05's six assertions and Build 06's design
review are the strongest existing checks in the repository, and they earn it:
the transposed plate, the shifted labels, the percentage stored where a
fraction is declared, the sample codes turned into dates by a spreadsheet and
the sub-microlitre transfer are all caught.

The one that goes through is the one the chapter is named for. A concentration
column in nanomolar under a micromolar header passes **every one** of Build
05's assertions. Rows are conserved, no nulls appear, the column name still
carries a unit, every value is inside the declared bounds, every well is on the
plate map, and two runs agree. The table is tidy, validated and a thousand
times wrong. Nothing in the file can catch it, because nothing in the file
knows what concentration the assay was supposed to use. `unit_plausibility`
compares against the declared assay band, which is information that has to come
from outside the file.

**Drift: 1 of 5 unaided.** Build 03 catches the criteria version changing
midway, because it stamps a version on every verdict. It catches nothing else,
and the reason is architectural rather than a missing check. The next section
is about that, because it is a limitation of the repository rather than of this
harness.

`drift.py` compares against the origin, never against the previous step, and
`test_the_wrong_drift_check_reports_nothing` demonstrates why rather than
asserting it. Fault `drift-04` walks from screening a corpus for viability
endpoints to comparing plasma protein binding. Against the origin the overlap
is 0.07 and the check fires. Step to step, no adjacent pair drops below 0.55,
so the obvious implementation reports nothing the entire way down. Both numbers
are computed from the same six sentences.

**Loop: 4 of 5 unaided.** Build 01's four orchestration decisions all work: the
step cap returns INCOMPLETE with `answer: None`, the circuit breaker withdraws
a tool after three consecutive failures, the write gate refuses a write with no
out-of-band approval, and a permanent API error stops the run.

The miss is a loop that repeats itself and still finishes. Four identical tool
calls, then an answer, then COMPLETE. Every call valid, every call allowed, the
cap never reached, nothing failed. Build 01 counts steps and does not compare
them.

**Identity: 1 of 4 unaided.** The exact duplicate identifier is caught. The
preprint and its published version, the same paper under two identifier
schemes, and two records differing only in whitespace and case all go through.

## The drift result is a limitation of the repository, not of the harness

One of five is the worst family score here, and it would be easy to read it as
a gap in the earlier builds' checks: somebody forgot to write a drift check,
and writing one would fix it. That reading is wrong and worth correcting,
because it points at the wrong repair.

**A drift check needs two things to compare, and this repository records one of
them almost nowhere.** Drift is the distance between what a run was asked to do
and what it is doing now. Measuring it requires the instruction as it was
given, kept verbatim for the length of the run, and a current objective to hold
against it. Neither Build 10's `RunManifest` nor Build 12's has any field for an
instruction at all, and here is what the traces actually contain:

| Build | What it records about its instruction |
|---|---|
| 01 | `run_start` carries `task` verbatim. The only one that does. |
| 03 | `run_start` carries the model and the step cap. Not the task. |
| 12 | `run_started` carries the question **identifier**, not its text. |
| 10 | The manifest has no field for an instruction. |

So exactly one build of twelve keeps the instruction, and it is the one that
never restates an objective, so there is nothing to compare it against there
either. There is no build in this repository where both halves exist at the
same time.

That is why `drift.py` supplies the run state itself for four of the five
faults. It is not a weakness in the fixtures being hidden: **the field does not
exist to be read**, and the harness cannot measure a distance from a point
nothing recorded. A drift check bolted onto Build 03 today would have nothing
to run against and would report CLEAN on every drifted run, which is a worse
outcome than the honest 1 of 5, because it would look like coverage.

The one drift fault that is caught is caught for exactly this reason in
miniature. `criteria_version_mismatch` fires because Build 03 stamps the
criteria version on every verdict, so a run screened under two versions has
recorded both and the comparison is possible. That is a drift check, and it
works, and it works because the thing to compare against was written down.

### What a fix would look like

Three changes, none of them a new detector.

**An `origin` field in the run manifest, carrying the instruction verbatim.**
Not an identifier, not a summary, and not regenerated from the current state.
Build 12 records `question.question_id`, which is enough to look the question
up and not enough to notice it stopped being the question being answered. The
text has to travel with the run.

**A `current_objective` written to the trace at each step**, alongside the step
number. This is the expensive half, because it means a stage that could
previously do its work silently now has to say what it thinks it is doing. It
is also the half that makes the origin useful: an instruction with nothing to
compare it against is provenance rather than a control.

**The comparison running before the output is written.** `GuardedPipeline` in
`adapters.py` is the shape: the check runs ahead of the stage that produces the
summary, so a run that has drifted is stopped rather than reported on after the
fact. `test_drift_is_detected_before_output` asserts that ordering on the event
log rather than trusting it.

The first two are small, and they are the ones that were skipped nine builds
ago because nothing needed them yet. The cost of adding them now is that every
build's trace grows a field and every agent loop grows a sentence about its own
purpose. The cost of not adding them is a family of failure the repository
cannot detect at all, and which currently scores 1 of 5 for a reason no amount
of work on the harness would improve.

## Prove the harness bites

Per the rule in `docs/CONVENTIONS.md`, a check that asserts
something cannot happen has to be shown failing first. Two parametrised tests
do it for every family:

- `test_each_family_has_a_fault_the_bare_builds_miss` names one fault per
  family that the earlier builds are recorded as missing, runs it against them
  with nothing added, and asserts it was missed **and that the miss was
  silent**. If a later change makes one of these pass, this fails and somebody
  has to decide whether a real check arrived or the fault stopped being one.
- `test_each_family_has_a_fault_something_catches` names one the builds catch,
  and asserts they still do. Where the bare builds catch nothing in a family at
  all, which is true of fabrication, that absence is recorded as `None` in the
  catalogue and asserted as zero rather than glossed over.

`test_the_added_checks_are_what_close_the_gap` pins both totals, 11 and 25, so
neither can move without a test failing.

## Subprocesses, not import gymnastics

The spec offers a choice. This build wraps each earlier build in a subprocess.

The root `conftest.py` keeps exactly one build importable at a time and
re-activates it before every test. An adapter that swapped Build 03 onto
`sys.path` in the middle of a Build 11 test would be fighting that mechanism,
and the failure when it went wrong would be the quiet one the mechanism exists
to prevent. A process boundary makes the invariant structural rather than
conventional.

It also keeps the measurement honest. A worker starts with exactly one build
folder on its path and no red-team module importable at all, which is the
situation a reader is in with one folder open. The harness cannot reach inside
a build to make it fail interestingly, because it cannot reach inside a build.

Five workers, started once and held open for the run, one JSON line per fault.
Each wires its build offline the way that build's own tests do.

`Outcome` keeps `build_checks` and `harness_checks` apart and merges them only
in `checks_fired`, which is what the printed `run_red_team` reads. That split is
what makes the two columns in the table above possible.

## The fifth family, and the listing

The chapter names four families and `harness.py` prints a closed `Literal` with
four values in it. That is the listing and it is not edited.

`families.py` carries the open set: a registry, a `register_family` that
requires a written reason, and `OpenFault`, which has the same five fields with
`family` validated against the registry. It is deliberately not a subclass of
`Fault`, because inheriting would make the open behaviour look like something
the book printed. `run_red_team` takes `list[Fault]` in its printed signature
and does not check it, because Python does not.

One consequence of the listing is worth knowing about: the printed
`FaultResult` constructor takes four arguments and family is not one of them,
so a result cannot carry a family. Fault identifiers are therefore
`<family>-<n>` and `Report` parses them. That is forced by the listing rather
than chosen, and it is written down in `harness.py` so the next person does not
decide it was an accident.

## Run it

```python
import catalogue
from harness import run_red_team

pipeline = catalogue.checked_pipeline("numeric")
try:
    report = run_red_team(pipeline, catalogue.planted("numeric"),
                          catalogue.clean_numeric())
finally:
    pipeline.close()

print(report.summary())
for result in report.results:
    print(result.fault_id, result.caught, result.fired)
```

Swap `checked_pipeline` for `bare_pipeline` to measure the earlier builds
without the checks this one adds.

## Tests

```
pytest builds/11-red-team/tests/
```

Twenty-one, none of which touches the network. The six the spec names are
present under those names. The run takes about thirty seconds, most of it
starting five Python interpreters.

## What is not here

No fuzzing and no generated faults. Every fault is a small deterministic
function, because a red team whose results move between runs cannot tell you
whether a check regressed.

No claim that the fault families are complete. The whole argument of the fifth
family is that they are not, and the registry exists so that the sixth costs a
function call rather than a model change.

No live metadata source in any test. `HttpMetadataSource` shows the shape and
nothing in the gate calls it.
