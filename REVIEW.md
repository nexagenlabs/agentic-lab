# REVIEW.md

Adversarial review of `agentic-lab` at `49da4aa`, performed against a fresh
clone in a temporary directory with a fresh virtual environment, not against
the working tree.

Nothing in this report was fixed. Findings only.

---

# Part 1: does it work

## Environment

Clone of `49da4aa` into a temporary directory. New venv, `pip install -r
requirements.txt`. No `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` in the
environment and no `.env` file present, confirmed before running.

Dependency resolution pulled versions materially newer than those the builds
were written against, which is a real test of the version caps and they held:
`anthropic 1.2.0`, `openai 3.6.0`, `pandas 2.3.3`, `numpy 2.5.2`,
`pandera 0.33.0`, `pydantic 2.13.5`, `langgraph 1.2.11`.

## Results

**277 passed, 0 skipped, 0 xfailed** in 146 seconds. `-rs` reported no skips.

Every gate also passes in isolation, and the counts reconcile exactly:

| Gate | Result |
|---|---|
| 01-first-agent | 11 passed |
| 02-tool-belt | 11 passed |
| 03-triage-agent | 14 passed |
| 04-dual-screen | 26 passed |
| 05-wrangler | 15 passed |
| 06-plate-mapper | 14 passed |
| 07-protocol-adapter | 26 passed |
| 08-dock-loop | 19 passed |
| 09-eln-bridge | 17 passed |
| 10-run-manifest | 16 passed |
| 11-red-team | 21 passed |
| 12-repurposing-desk | 15 passed |
| tests/ (root) | 72 passed |
| **sum** | **277** |

205 in builds, 72 at the root. No gate passes together and fails apart, or the
reverse.

`ruff check .` is clean, but see finding 1.1.

## Finding 1.1: `ruff` is not installable from `requirements.txt`

**Severity: moderate. Affects every reader.**

`CLAUDE.md` makes `python -m ruff check builds/<name>/` point 2 of the
definition of done. `README.md` tells a reader to run
`pip install -r requirements.txt`. That install does not provide ruff:

- `requirements.txt` does not mention ruff.
- `requirements.lock.txt` line 46 pins `ruff==0.16.5`.
- `README.md` never mentions ruff at all.

So a reader who follows the printed setup gets `No module named ruff` when they
try the second of the two gates the project defines for itself. I had to
install ruff by hand before I could run it, which means the lint gate has
probably only ever been run in an environment that had it for unrelated
reasons.

The lock file is not a workaround: nothing tells the reader to use it, and
`README.md` names `requirements.txt`.

## Finding 1.2: `CLAIMS.md` is not in the repository

**Severity: moderate for this review; low for readers.**

The file this review's Part 2 is based on is untracked. It exists in the
working tree and has never been committed:

```
$ git log --all --oneline -- CLAIMS.md     # no output
$ git status --short
?? CLAIMS.md
```

It is therefore absent from the clone, and absent from what any reader or
reviewer downloads. Part 2 below was performed by reading it out of the working
tree. If the intent is that claims are checkable by anyone, the file has to be
committed; if the intent is that it is a private worksheet, then nothing in the
repository records what the book asserts about the code.

## Deliberate breakage: what is caught

I removed or corrupted things and looked for silence. Loud failures are good
news and are listed for completeness; the silence is the finding.

| Change | Result |
|---|---|
| Delete `builds/03-triage-agent/fixtures/corpus/99000001.json` | **caught**, 3 failures including `test_fixture_corpus_is_internally_consistent` |
| Delete `builds/08-dock-loop/fixtures/vina_output/KIN-BETA__DEC-001.pdbqt` | **caught**, `test_decoy_enrichment_exceeds_threshold` |
| Delete `builds/09-eln-bridge/fixtures/injection/01_annotated_protocol.json` | **caught**, 2 failures |
| Delete a Build 06 broken design fixture | **caught**, `test_bad_designs_are_rejected` |
| Delete a Build 05 broken export fixture | **caught**, `test_schema_rejects_known_corruptions` |
| Delete `builds/10-run-manifest/fixtures/dirty_run/` | **caught**, `test_dirty_tree_is_recorded` |
| Delete a listing file from `listings/ch05/` | **caught**, listing conformance |
| Delete `builds/12-repurposing-desk/fixtures/known_answer/` | **caught**, `test_shortlist_matches_known_answer` |
| Rename `builds/05-wrangler` to `builds/05-wrangler-renamed` | **caught**, 14 failures across listings, site URLs, Build 11 and Build 12 |
| Flip one hex character of an input `sha256` in Build 10's `stored_run/manifest.json` | **caught**, 5 failures |
| Empty `builds/03-triage-agent/criteria/repurposing_v3.yaml` | **caught**, 4 failed and 12 errors, including collection errors in Build 12 |

Fixture deletion is well defended. Every fixture I removed was anchored by a
count, a gold set or an expectation file rather than merely globbed.

## Finding 1.3: five provenance fields are recorded and never verified

**Severity: high. This is the one that matters in Part 1.**

I tampered with fields in Build 10's committed
`fixtures/stored_run/manifest.json`, one at a time, and re-ran that build's
gate:

| Field tampered | Result |
|---|---|
| `approvals` | **16 passed. Silent.** |
| `mapping_ids` | **16 passed. Silent.** |
| `design_ids` | **16 passed. Silent.** |
| `python_version` | **16 passed. Silent.** |
| `halt_reason` | **16 passed. Silent.** |
| `git_commit` | caught, 1 failure |

Four of these are the block the printed Chapter 9 listing labels **"decisions
carried from earlier chapters"**: `criteria_version`, `mapping_ids`,
`design_ids`, `approvals`. Three of the four can be replaced with the string
`TAMPERED` and the entire Build 10 gate still passes.

This matters more than a normal untested field, because the argument of Chapter
9 is that a manifest is what lets you reconstruct a run, and the argument of
Chapter 8 is that an approval is worthless unless it is auditable. `approvals`
is the field carrying Build 09's approver identities into the manifest, and
nothing checks it at all. A manifest that records provenance nobody verifies is
the decorative manifest the chapter warns about, one level up.

`halt_reason` is a related but separate gap: a run with `status: COMPLETE` and
a non-null `halt_reason` is incoherent, and nothing rejects it.

## Part 1 verdict

The suite is genuinely green from a clean clone with no key, the isolation
mechanism holds under individual and combined runs, and fixture deletion is
well defended. Two real defects: the lint gate is not installable from the
documented install, and a block of manifest provenance fields is recorded
without ever being verified.

---

# Part 2: is the book true of the code

`CLAIMS.md` holds 76 claims. Each was checked against the code in the clone,
and behavioural claims were checked by running them rather than by reading.
`SPEC.md` and the build READMEs were not used as evidence.

**Note on provenance of this section:** `CLAIMS.md` is untracked and is not in
the clone (finding 1.2). It was read from the working tree.

## Summary

| Verdict | Count |
|---|---|
| TRUE | 69 |
| TRUE, but the wording overstates it | 5 |
| **FALSE** | **3** |
| UNVERIFIABLE | 2 |

Three claims are false. Two are small and one is not.

## FALSE

### C3.1 the printed loop is not 28 non-blank lines

**FALSE.** The book states the printed loop is 28 non-blank lines.

- `listings/ch03/03_stage3_the_loop.txt` is **26** non-blank lines in total,
  including `import json` and `MAX_STEPS = 20`.
- `run_agent` itself, `builds/01-first-agent/stage3.py:95-120`, is **24**
  non-blank lines.

Neither figure is 28. The related claim that the loop "fits in about sixty
lines" is true but loose: it is a third of that. The claim that it "remains
recognisable inside `agent.py`" is true, `builds/01-first-agent/agent.py:220`,
where the same loop is 109 non-blank lines with the limits, the trace and the
error policy around it.

This is a number in the book the code does not produce, and it is the kind a
reader can check in ten seconds with a text editor.

### C5.1 "the agent never touches a number" is not true as written

**FALSE as worded. True in the sense intended, and the distinction matters.**

The agent emits no numeric value. But it emits `detected_unit`, described in
`builds/05-wrangler/models.py:17` as "what the agent believes it found", and
that string selects a multiplier applied to every concentration in the file:

- `builds/05-wrangler/transform.py:113-117` `concentration_unit()` returns the
  mapping's `detected_unit`.
- `builds/05-wrangler/transform.py:104-110` `_to_nanomolar()` looks that
  string up in `TO_NM` and multiplies the column by it.

So a model output determines whether every concentration is multiplied by one
or by a thousand. The agent does not produce the number; it selects the
factor, which is the same failure with an extra step in it.

What actually stands between that and a silent thousandfold error is the human
approval gate, `builds/05-wrangler/transform.py:49`, which refuses a mapping
whose `approved_at` is unset. That is a good defence and the book should claim
it, rather than claiming the agent never touches a number.

This is not academic. Build 11's `numeric-01` is exactly this error, and it is
the one numeric fault the earlier builds miss silently.

### X.5 the repository contains an en dash

**FALSE.** One file, committed:

```
references/references_report.md:167
  found:   Searching for Drug Synergy in Complex Dose–Response Landscapes
           Using an Interaction Potency Model
```

It is also in `references/references_resolved.json`, for `yadav2015zip`.

It arrived from Crossref: the publisher's own registered title uses an en dash,
and the verification tool wrote the returned title verbatim, which is correct
behaviour. Altering a quoted title to satisfy a house style would be worse than
breaking the style.

The real finding is underneath: **nothing enforces this rule.** There is no
test for dashes anywhere in `tests/` or any build's tests. A house rule stated
in `CLAUDE.md` as "checked" has been checked only by hand, every session, by
whoever remembered.

## UNVERIFIABLE

### C7.4 `prediction_confidence` is specified over the pocket

`builds/08-dock-loop/models.py:31` carries the comment "mean pLDDT over the
pocket" and the validator at line 47 enforces that a predicted structure has
one and an experimental structure does not. Nothing enforces, or could
enforce, that the float supplied was computed over the pocket rather than the
whole chain. It is a documentation claim about a caller's discipline. The
fixtures are fabricated, so there is no ground truth to check it against.

### C3.2 "the model appears only at steps two, four and six"

The verifiable half is TRUE: exactly one model call per turn of the loop,
`builds/01-first-agent/agent.py:256`, the only `messages.create` in the
function. The seven-step narrative and the numbering of those steps exist only
in the book's prose and cannot be checked against code.

## TRUE, but the wording overstates it

- **C2.1** Each build reads its model from one `config.py`, which is what the
  claim's own test asks, so TRUE. But "a model change is one line rather than
  forty" is not true of the repository: there are **five** distinct environment
  variables (`AGENT_MODEL`, `SCREEN_A_MODEL`, `SCREEN_B_MODEL`,
  `AGENT_MODEL_CHEAP`, `AGENT_MODEL_FRONTIER`) across eight `config.py` files.
  Setting `AGENT_MODEL` alone leaves Build 04's screen B and two of Build 12's
  three tiers on their old models, silently. `MODELS.md` compounds this by
  saying "updating this page and that file is the whole migration", singular.
- **C4.8** The gold set is rule-defined and its size is an output, TRUE. But
  the negatives component is a caller-supplied fixed count, `GOLD_NEGATIVES`,
  `builds/04-dual-screen/goldset.py:89`. The code's own docstring says so.
- **C5.5** Units live in column names, TRUE for `conc_nM`. The exception is
  `viability`, `builds/05-wrangler/schema.py:25`, which carries no suffix. See
  Part 3: it is the one column whose unit ambiguity has its own named failure
  fixture.
- **C7.8** Enrichment is measured against property-matched decoys, TRUE, but
  matched on molecular weight and logP only. Build 08's fixture README states
  this; the book's phrase "property-matched" is doing more work than the
  fixture supports.
- **X.4** No build imports another build, TRUE, confirmed by grep for
  `from builds` and `import builds`. But Build 12 hard-codes filesystem paths
  into five other build folders, `builds/12-repurposing-desk/stages.py:62-66`,
  and Build 11 does the same through `adapters.py:97`. Renaming a build folder
  breaks both, which Part 1 demonstrated.

## TRUE, verified by running

These were confirmed by execution rather than reading:

| Claim | Measured |
|---|---|
| C3.7 tool disabled after three failures, model told | tools offered dropped to `['save_note']` at call 4; `tool_disabled` returned when asked |
| C6.6 the printed design fits its plate | 40 combinations + 12 controls = 52, interior wells = 60 |
| C6.7 each replicate its own plate | `plates = 3`, `replicates = 3` |
| C6.8 randomisation reproducible, different seed differs | both hold |
| C7.7 redocking within two angstroms | 1.129 |
| C10.8 11 of 25 caught bare, all misses silent | 11 of 25; 14 missed; 14 silent |
| C12.4 routing an order of magnitude cheaper, shortlist unchanged | 7.27 against 71.95, ratio 9.9, identical shortlist |
| C12.7 no antiparasitic in the shortlist | `['clozapine', 'chlorpromazine', 'diclofenac']` |
| X.1 no test touches the network | 277 pass with `connect`, `connect_ex`, `create_connection` and `getaddrinfo` all denied |
| X.2 impossibility tests bite | three broken deliberately, all three failed: Build 09 `update_record` added, Build 11 duplicate check forced, Build 12 checkpoint made non-blocking |
| X.3 clean clone, no key | 277 passed |

The remaining claims were verified by reading, each against a named file and
line, and each is backed by a passing test under the name the claim implies.

---

# Part 3: what would embarrass us

## 3.0 A correction to Part 2, found while doing Part 3

**C12.7 is FALSE, and I marked it TRUE.**

I verified it the shallow way: I checked whether the shortlist contained an
antiparasitic, saw that it did not, and moved on. The claim is not about the
shortlist. It is about *why*, and the stated cause is wrong. Section 3.4.

## 3.1 Documented rather than enforced: three instances, so a pattern

Finding 1.3 was not isolated. The same shape appears three times, in three
different builds, and each time it is the property the surrounding chapter is
arguing for.

**(a) Build 10, manifest provenance.** Finding 1.3. `approvals`,
`mapping_ids`, `design_ids`, `python_version` and `halt_reason` can each be
replaced with `TAMPERED` and the gate stays green.

**(b) Build 09, machine attribution.** `builds/09-eln-bridge/notebook.py`,
`authorise()`, refuses a write whose `model_id`, `model_version` or `run_id` is
missing. Disabling that loop entirely gives:

```
attribution_missing disabled -> 17 passed
```

Chapter 8 says every entry the build writes carries machine attribution.
Nothing checks that the guard exists. Its sibling in the same function,
`not_approved`, is properly covered: disabling that one fails a test at once.

**(c) Build 05, the sixth assertion.** Neutering each of the six assertions the
book names as Table 5.2, one at a time:

| Assertion neutered | Result |
|---|---|
| `assert_row_conservation` | 1 failed |
| `assert_no_silent_nulls` | 3 failed |
| `assert_units_declared` | 1 failed |
| `assert_ranges_plausible` | 1 failed |
| `assert_identifier_integrity` | 1 failed |
| **`assert_deterministic`** | **15 passed. Silent.** |

Five of six bite. The sixth can be deleted and nothing notices.

In fairness: the determinism *property* is covered by
`test_transform_is_deterministic`,
`builds/05-wrangler/tests/test_wrangler.py:158`, which compares bytes and
column order itself, so C5.9 stands. What is untested is the assertion inside
the shipped pipeline, which is the part a reader copies into their own code.

**(d) A fourth, weaker instance: Build 04 screen independence.** I marked C4.13
TRUE in Part 2 because `run_screen` has no parameter through which screen B
could receive screen A's verdicts, and `build_task_a` and `build_task_b` both
take only `(record, criteria)`. That remains true, and `plan_screens` genuinely
refuses same-model and unacknowledged `same_agent_twice` configurations. But
independence is guaranteed by *the absence of a channel*, not by an assertion.
Nothing would catch a `prompt_builder` that closed over screen A's output.
Structural absence is a good defence and it is not enforcement, and no test
states the property.

**The pattern:** in each case the unchecked thing is the one its chapter is
about. Provenance in the provenance chapter, attribution in the attribution
chapter, determinism in the reproducibility chapter, independence in the
independence chapter. A reviewer who reads a chapter and greps for a test of
its central claim comes up empty four times out of four.

## 3.2 Which numbers a reader can check, and which they must take on trust

**Checkable. A reader can recompute these from the repository:**

| Number | Verified |
|---|---|
| 11 of 25 caught by the earlier builds, 14 misses, all silent | recomputed exactly |
| 9.9x routing saving, identical shortlist | recomputed |
| 40 combinations plus 12 controls inside 60 interior wells | recomputed |
| 3 plates for 3 replicates | recomputed |
| 61 corpus records, 12 include, 3 flag, 57 of 61 agreeing with gold | recomputed |
| 24 of 24 references resolving by DOI | recomputed |

**Take on trust. Fabricated, and in two cases the generator sets the number the
test then checks:**

| Number | Why it cannot be checked |
|---|---|
| **1.13 angstrom redocking RMSD** | `builds/08-dock-loop/fixtures/make_fixtures.py:126` sets `step = 1.13 / sqrt(3)`, so the RMSD is exactly 1.13 by construction. The test asserts it is under 2.0. The fixture encodes its own pass. |
| **3.6 enrichment factor** | actives drawn from `rng.gauss(-9.1, 0.75)`, decoys from `rng.gauss(-7.9, 0.75)`, fixed seed, `make_fixtures.py:192`. The separation is chosen and the threshold is 2.0. |
| every docking score, IC50, PMID, DOI and cell count | fabricated |
| the Chapter 12 shortlist | section 3.4 |

Build 08's `fixtures/README.md` is admirably explicit that these are
constructed and why. **The book has to be equally explicit.** A reader who
meets "the fixture recovers it to 1.13 angstroms" in prose, without that
context, reads a measurement. It is a stipulation.

## 3.3 Fixtures arranged so their own check cannot fail

The redock fixture and the enrichment fixture, above. Both are honest about it
inside the repository, and both would read as results on a page.

This is not a criticism of the fixtures, which have to come from somewhere. It
is a criticism of any sentence in the book that presents them as findings.

## 3.4 The one that would actually embarrass us

**Chapter 12's closing failure account gives the wrong cause, and the real
cause is a 0.1 margin in a pseudo-random number.**

The book says the desk's shortlist contains no antiparasitic **because the
corpus does not suit the question**. That explanation is false.

The corpus contains antiparasitics that survive screening. PMID 99000009 is
screened **include** and names albendazole and mebendazole. Both are in the
question's `compound_ligands` map, both were docked. The full ranking of
everything that survived screening:

```
 1. clozapine        ACT-004  -9.6
 2. chlorpromazine   ACT-003  -9.3
 3. diclofenac       ACT-005  -9.1   <-- shortlist cut, n = 3
 4. albendazole      ACT-001  -9.0   <-- ANTIPARASITIC
 5. rifampicin       DEC-007  -8.9
 ...
16. mebendazole      DEC-002  -6.6   <-- ANTIPARASITIC
```

**An antiparasitic missed the shortlist by 0.10 kcal/mol**, on a score produced
by `rng.gauss` under seed 20260829.

Three arbitrary choices decide the chapter's ending:

1. `shortlist_n: 3` in `fixtures/question.yaml`. Set it to 4 and an
   antiparasitic is in the shortlist.
2. The alphabetical compound-to-ligand assignment, which happens to hand
   albendazole `ACT-001`, an active rather than a decoy.
3. Build 08's fixture seed.

None of these is science, and I chose two of them.

**Nothing in the suite pins it.** `test_shortlist_matches_known_answer` pins
the top three, so a regenerated Build 08 fixture set would fail that test
loudly, which is good. But the book's *argument* would become false silently at
the same moment, and no test speaks to the argument.

The honest version is stronger than the printed one, not weaker: the desk
ranked an antiparasitic **fourth of sixteen**, and a reader looking at a
top-three shortlist would never learn that the thing they asked about came
fourth. That is a real and demonstrable limitation of shortlisting, and it does
not depend on the corpus being a poor fit.

I should have caught this in Part 2. I checked the claim's first clause and not
the word "because".

## 3.5 Smaller things a hostile reviewer would enjoy

- **`ruff` is not installable from the documented install.** Finding 1.1. The
  first thing a reviewer does is follow the README.
- **`viability` is the one schema column with no unit suffix**,
  `builds/05-wrangler/schema.py:25`, in the build whose rule is that units live
  in column names, and it is the exact column with its own named failure
  fixture, `percentage_as_fraction.csv`. `conc_nM` carries its unit;
  `viability` does not say fraction or percentage.
- **The en dash**, and more importantly that the no-dash rule has no test at
  all, while `CLAUDE.md` describes it as checked.
- **The QR damage figures were measured on one code**, `ch07.png`, and
  `qr/README.md` presents them as properties of the set. `references.png` is a
  denser version 5 symbol and was never damaged.
- **Five environment variables, not one**, and `MODELS.md` saying "that file"
  singular when there are eight.

## 3.6 What held up

Stated with the same prominence, because a review listing only faults is as
misleading as one listing none.

- **Fixture deletion is genuinely well defended.** Eight deletions across six
  builds, every one caught, because fixtures are anchored by counts, gold sets
  and expectation files rather than merely globbed.
- **Assertion mutation is mostly well defended.** Five of six Build 05
  assertions, Build 09's approval guard and Build 10's `verify_inputs` all fail
  a test when neutered.
- **No test touches the network.** 277 pass with `connect`, `connect_ex`,
  `create_connection` and `getaddrinfo` all denied.
- **No dependence on being a git checkout.** 277 pass with `.git` deleted, so a
  reader who downloads a ZIP gets the same result.
- **The version caps held** against dependencies one to two majors newer than
  those the builds were written against.
- **The isolation mechanism holds**, individually and together, and the counts
  reconcile exactly.

## Closing

Four defects worth acting on, in order: the wrong causal claim closing Chapter
12; the recorded-but-unverified pattern across Builds 05, 09 and 10; the
numbers the book presents as measurements that are stipulations; and `ruff`
being uninstallable from the documented install.

The repository is in better shape than the book is. Every one of the three
FALSE claims in Part 2 and the fourth found in Part 3 is a defect in the prose
rather than in the code, and each is a sentence written from intention before
there was a running system to check it against.

---

# Corrections, added after the review

Appended rather than folded into the findings above. A review edited until it
agrees with what was later learned is a review nobody can audit, and the
distance between what was concluded and what turned out to be true is the most
useful thing in this file.

## 1.13, 3.6 and "11 of 25" are not in the manuscript

**Author's correction, 2026-08-30. Sections 3.2, 3.3 and the closing list are
wrong about where these numbers appear.**

The author grepped all fifteen manuscript files. `1.13`, `3.6` and `11 of 25`
return zero hits each. They appeared in build reports written by earlier
sessions, and this review read those reports as though they were the book. No
sentence in the book presents a stipulated fixture value as a measurement,
because no sentence in the book mentions these values at all.

What falls away: the claim that the book prints stipulations as findings, and
the three REQUIRED book items that followed from it.

What stands, unchanged, because it is a fact about the code rather than about
the manuscript:

- `builds/08-dock-loop/fixtures/make_fixtures.py:126` sets
  `step = 1.13 / sqrt(3)`, so the redocking RMSD is 1.13 by construction and
  the fixture encodes its own pass.
- The enrichment separation is drawn from two fixed distributions at a fixed
  seed.
- A test asserting a constructed value clears a threshold the construction was
  built to clear is decoration, whatever the book does or does not say.

The distinction matters for what happens next: these are now code and fixture
questions with no print deadline attached, rather than sentences that had to
change before the book went to press.

## 3.9, the end-to-end gate, does not reproduce

**Checked 2026-08-30, at `2a53a77`, and the finding is wrong.**

The claim in circulation was that Build 12 recomputes what its gates check, so
`test_all_prior_gates_pass_in_sequence` cannot fail on a defect in Builds 01 to
11. It can, and it does.

`TO_NM["uM"]` in `builds/05-wrangler/transform.py:41` was changed from `1000.0`
to `1.0`, a silent thousandfold unit error. Build 05's own gate reported 1
failed, 14 passed. Build 12's end-to-end test then failed in 74 seconds with
`AssertionError: 05-wrangler failed 1 of 15`, naming the build. The test shells
out to pytest over the eleven build gates and the root suite, parses the JUnit
XML, and asserts per build that there were no failures. The mechanism is
build-agnostic.

What is true nearby, and is a different sentence: the desk *run* is Build 12's
own implementation. `stages.py:63-67` reads five other builds' fixture
directories by path and never executes their code. So the earlier builds are
exercised by their own gates inside that subprocess, not by the shortlist
moving.

One real weakness was found while checking, and is fixed: the gate asserted
`counts["tests"] > 0` and a total above 200 against an actual 263, so deleted
tests were invisible until a whole build reached zero. Per-build counts are now
anchored in `EXPECTED_TESTS`.

## `test_row_conservation`: checked, and the framing does not hold

**Checked 2026-08-30 at `74b1ba4`. Recorded because it was asked for by name,
and it is not what it was thought to be.**

The claim was that `test_row_conservation` proves the assertion function works
and not that the pipeline calls it. It proves both. The test drives
`pipeline.run`, not `assert_row_conservation`,
`builds/05-wrangler/tests/test_wrangler.py:61-78`, and two separate mutations
confirm it:

- Neutering the condition inside `assert_row_conservation` fails
  `test_row_conservation`. This is the mutation gate's `row_conservation`
  entry, and it is in `CAUGHT` for this reason.
- Deleting the *call* from `pipeline.run` also fails it.

The second probe was run over all six call sites, because a guard that is
called nowhere would pass a condition mutation and look identical to a guard
nobody tests:

| Call removed from `pipeline.run` | Result |
|---|---|
| `assert_row_conservation` | caught, `test_row_conservation` |
| `assert_no_silent_nulls` | caught, `test_schema_rejects_known_corruptions` |
| `assert_units_declared` | caught, same |
| `assert_ranges_plausible` | caught, same |
| `assert_identifier_integrity` | caught, same |
| `assert_deterministic` | **15 passed. Silent.** |

Five of six call sites are verified reachable and checked. The sixth is the
survivor already recorded as PLAN B4, and it now has a second piece of evidence
against it: not only can the comparison be removed, so can the call.

**What is true, smaller, and new.** Of the six numbered assertions, four have a
broken fixture declaring which assertion should fire: 2 in `excel_mangled`, 3
in `extra_column` and both `unit_collision` files, 4 in
`percentage_as_fraction`, 5 in `shifted_labels` and `transposed_plate`.
Assertions **1 and 6 have none**. Row conservation is demonstrated by raising
the declared expectation to `WELLS + 1` rather than by an export that lost a
row, so no fixture in the set ever shows the pipeline detecting a real row
loss. The comparison is the same either way, `actual != expected.expected_rows`,
so this is a gap in the fixture set rather than a hole in the coverage, and it
is recorded at that size.

## What the mutation gate cannot tell you

**Read this before quoting a mutation score.**

A surviving mutant means one thing only: the named test still passed after that
text changed. Three different situations produce it and the harness cannot
distinguish them.

1. **Nothing tests the guard.** The case the gate exists to find.
2. **Nothing can reach the guard.** A condition that is already unreachable
   cannot be made more unreachable, so dead code scores exactly like untested
   code. This is the reading that flatters the repository and it is the one to
   rule out first.
3. **The mutation was semantically null.** An anchor that no longer matches
   what the guard does, or a replacement that happens to preserve behaviour,
   both report a clean pass. `test_every_guard_in_the_registry_is_reachable`
   catches the first of those and nothing catches the second.

Telling them apart takes a second probe and a human reading of the guard. The
call-site table above is an example: neutering `assert_deterministic`'s
comparison and deleting its call from the pipeline both survive, which rules
out unreachability and leaves case 1.

So the number is a floor on what is untested, never a measure of what is
tested. Eleven of fourteen guards caught says eleven guards have a test that
notices their removal. It says nothing about the other several hundred lines
of each build, and a run with no survivors would not mean the suite is
complete. It would mean these fourteen anchors are covered.
