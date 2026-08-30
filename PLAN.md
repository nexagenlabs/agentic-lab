# PLAN.md

Remediation plan for the findings in `REVIEW.md`, at `556546d`.

Nothing here is implemented by this document. Four items are implemented in
the same session under a separate commit, and they are marked DONE and listed
again at the end with what changed.

## How this is ordered

Severity is the obvious ordering and it is the wrong one on its own. The
constraint that actually ranks this work is **which fixes stop being available
at print**. A wrong sentence on a page cannot be patched; a missing test can be
added in the first week after release and nobody is harmed in the meantime.

So the order is:

1. Statements printed on paper that are not true of the code.
2. Choices that freeze at print because a listing prints them: a column name,
   a field name, a number in a caption.
3. Code that verifies nothing, in the place its chapter says it verifies
   something.
4. Everything else.

Three of the four items in group 1 are in Chapter 7 and Chapter 12.

---

## Summary table

| # | Finding | Fix in | Required before print | Needs a ruling |
|---|---|---|---|---|
| A1 | 3.4, Chapter 12's closing failure gives the wrong cause | both | **yes** | no |
| A2 | 3.2, 1.13 angstroms printed as a measurement | both | **yes** | no |
| A3 | 3.2, 3.6 enrichment printed as a measurement | both | **yes** | no |
| A4 | 3.3, the redocking control is a fixture replay | book, or code | **yes** | **yes** |
| A5 | C3.1, the loop is not 28 non-blank lines | both | **yes** | no |
| A6 | C5.1, "the agent never touches a number" | book | **yes** | no |
| A7 | C2.1, "one line rather than forty", five variables | both | **yes** | no |
| A8 | 3.5, `viability` carries no unit | both | **yes** | **yes** |
| A9 | 3.5, QR damage figures measured on one code of thirteen | repo tooling | **yes** | no |
| B1 | 1.3, manifest fields recorded and never verified | code | **yes** | **yes** |
| B2 | 1.3, `COMPLETE` with a non-null `halt_reason` | code | **yes** | no, DONE |
| B3 | 3.1b, Build 09 attribution guard is uncovered | code | **yes** | no |
| B4 | 3.1c, Build 05 `assert_deterministic` is uncovered | code | **yes** | no |
| B5 | 3.1d, screen independence is structural, not asserted | code, or book | **yes** | **yes** |
| B6 | 3.4, no test pins the Chapter 12 argument | code | **yes** | no |
| B7 | 1.1, `ruff` is not installable from the documented install | code | **yes** | no, DONE |
| B8 | X.5, the no-dash rule has no test | code | **yes** | no |
| C1 | 1.2, `CLAIMS.md` untracked | code | yes | no, DONE |
| C2 | C7.8, "property-matched" means two properties | book | desirable | no |
| C3 | C4.8, the gold set's negative count is supplied | book | desirable | no |
| C4 | X.4, Build 12 hard-codes paths into five builds | code | desirable | no |
| C5 | C7.4, `prediction_confidence` over the pocket | neither | no | no |
| C6 | C3.2, the seven-step narrative | neither | no | no |
| D1 | A real docking engine behind the stub | code | desirable | **yes** |
| D2 | Assertion mutation as a permanent gate | code | desirable | no |
| D3 | `ruff` and the lint gate named in `README.md` | code | desirable | no |

Two items on the author's REQUIRED list are not on this table, because they
have no target in the repository. See "Two required items with nothing to fix".

---

## Group A: printed statements that are not true

### A1. Chapter 12's closing failure gives the wrong cause

**REVIEW 3.4. The most serious finding in the review, and the one I would fix
first even though it is the least expensive.**

Fix in **both**, required before print.

*Book.* The printed cause, that the corpus does not suit the question, is
false: the corpus contains antiparasitics that survive screening, and one of
them ranked fourth of sixteen and missed a shortlist of three by 0.10 kcal/mol.
Replace the cause with the real one. The real one is a better ending: a reader
looking at a top-three shortlist never learns that the compound class they
asked about came fourth, and that is a demonstrable property of shortlisting
rather than an accident of the corpus.

*Code.* B6, below. The book's argument currently has no gate.

The book must also say, in that section, that the ranking comes from
fabricated scores under a fixed seed, because the 0.10 margin is a property of
`rng.gauss` and not of pharmacology. That does not weaken the point: the point
is about what a shortlist hides, and it holds for any margin.

### A2 and A3. 1.13 angstroms and 3.6 enrichment printed as measurements

**REVIEW 3.2 and 3.3.**

Fix in **both**, required before print.

*Book.* Neither number may appear in a sentence that reads as a result.
`fixtures/make_fixtures.py:126` sets `step = 1.13 / sqrt(3)`, so the redocking
RMSD is 1.13 by construction; the enrichment separation is
`rng.gauss(-9.1, 0.75)` against `rng.gauss(-7.9, 0.75)` at a fixed seed. Both
are stipulations. Build 08's `fixtures/README.md` already says so plainly, and
the book has to be as plain as its own fixture README.

*Code.* Small and non-negotiable: the two tests should read as demonstrations
of the arithmetic rather than as controls that passed. The geometry is real,
`geometry.rmsd` genuinely computes the number, and that is worth keeping and
worth naming honestly. `test_redocking_control_recovers_pose` already pins
`1.13 +/- 0.01`, which is good, and also asserts `control.passed` against a
2.0 angstrom threshold, which is the decorative half: the fixture was
constructed to clear it. Either drop the threshold assertion or move the
declared value into an expectation file beside the fixture, per the rule in
`CLAUDE.md` about a test that computes its number from the fixture data it is
checking.

I disagree with putting these entirely in the book. The book sentence is the
serious half. The `assert control.passed` line is the same defect one level
down and it is four characters of work.

### A4. The redocking control is a fixture replay

**REVIEW 3.3. Needs the author's ruling, which is why nothing is proposed
here.**

Fix in **book**, or in **code** as D1. Required before print either way.

Chapter 7's own sentence is that a setup which cannot recover a known answer
says nothing worth reading about an unknown compound. The repository has no
such setup: it has a stub engine replaying a pose that was generated to be
1.13 angstroms from the crystal one.

The two options are not equal in cost:

- **Say it is a replay.** Available now, costs a paragraph, and is honest. The
  chapter keeps its argument, which is about what a control is *for*, and
  gains a sentence saying the repository demonstrates the control's arithmetic
  rather than performing one.
- **Make the control real.** Needs AutoDock Vina, a real receptor and ligand
  pair, and a test that does not run it, because `CLAUDE.md` forbids tests
  that need anything installed. So a real engine ships as an optional path
  with the stub still under the gate, and the printed number becomes one the
  reader can reproduce only if they install Vina.

My recommendation: do the book fix now, and treat D1 as post-print work that
turns a printed stipulation into a printed measurement in a second edition.
The book fix does not become unnecessary if D1 lands later; the first printing
is the thing at risk.

### A5. The loop is not 28 non-blank lines

**REVIEW C3.1.** Fix in **both**, required before print.

`listings/ch03/03_stage3_the_loop.txt` is 26 non-blank lines; `run_agent` in
`stage3.py` is 24. Neither is 28. `builds/01-first-agent/README.md:50` repeats
the wrong number in the repository, so the book fix has a repository half.

"About sixty lines" is true and loose, not false: the loop is well under
sixty. I would keep "well under sixty lines" or drop the figure. The 28 is the
one a reader checks in ten seconds, and it is the one that must go.

### A6. "The agent never touches a number"

**REVIEW C5.1.** Fix in **book**, required before print.

The agent emits `detected_unit`, and that string selects the multiplier
applied to every concentration in the file, `transform.py:104-117`. Selecting
the factor is the same failure as producing the number, with one step in
between. Build 11's `numeric-01` is exactly this fault.

The replacement sentence is stronger than the printed one. What stands between
a model's unit guess and a silent thousandfold error is the approval gate at
`transform.py:49`, which refuses a mapping with no `approved_at`. Claim the
gate, which exists and is tested, rather than an absolute that is not true.

### A7. "One line rather than forty", and five environment variables

**REVIEW C2.1.** Fix in **both**, required before print.

There are five model variables across eight `config.py` files: `AGENT_MODEL`,
`SCREEN_A_MODEL`, `SCREEN_B_MODEL`, `AGENT_MODEL_CHEAP`,
`AGENT_MODEL_FRONTIER`. Setting `AGENT_MODEL` alone leaves Build 04's screen B
and two of Build 12's three tiers on their old names, silently, which is the
exact failure the claim promises does not happen.

*Book.* State the number, and state that the multiplicity is deliberate:
Build 04 needs two different models or the independence argument collapses,
and Build 12 needs three or the routing argument does.

*Repository.* `MODELS.md` says "updating this page and that file is the whole
migration", singular, with eight files. Correct that sentence.

**Found while writing this plan, not in the review:** `MODELS.md`'s
"Representative models" column is empty in all four rows. `README.md` sends
the reader there for "the current list, with a dated changelog" and the list
has no entries. That is a required fix before print and it is five minutes of
typing, but it is a fact about the repository today rather than a finding of
the review, so it is recorded here rather than folded into A7.

### A8. `viability` carries no unit

**REVIEW 3.5. Needs a ruling, and needs it before print rather than after.**

Fix in **both**. Required before print because the decision freezes at print:
`listings/ch05/04_pandera_schema.txt` prints the column name, so renaming the
column after publication breaks a printed listing, which is the one defect
this project treats as unshippable.

Convention 6 is that units live in column names. `conc_nM` obeys it.
`viability` does not, in the build whose chapter argues for the rule, and it
is the one column with its own named failure fixture,
`percentage_as_fraction.csv`, for the exact ambiguity the missing suffix
leaves open.

Options, cheapest first:

- **Leave the name and soften the book.** The rule becomes "units live in
  column names where a quantity has a unit", and viability is a dimensionless
  fraction. Honest, and slightly weaker than the chapter wants.
- **Rename to `viability_frac`.** Obeys the rule the chapter states, changes
  one printed listing and every fixture and test that names the column. Must
  happen before print or never.

I lean to the rename, because the chapter's argument is the strong form and
the fixture that exists is evidence the weak form is not enough. But this is
the author's call and the deadline for making it is the print date.

### A9. QR damage figures measured on one code

**REVIEW 3.5.** Fix in **repository tooling**, required before print.

`qr/README.md` presents twenty per cent contiguous, twenty-three per cent
failing, ten per cent speckle and any corner damage as properties of the set.
They were measured on `ch07.png`, a version 4 symbol at 33x33.
`references.png` is version 5 at 37x37 and was never damaged. A typesetter
reads that README and applies the numbers to whichever code is on the page in
front of them.

Fix: run the same damage measurement over `references.png`, and either report
per-symbol figures or state the figures as the worst case across the set.
Cheap, and it is the file whose whole purpose is to be trusted by somebody
laying out a page.

---

## Group B: code that verifies nothing where its chapter says it does

REVIEW 3.1 is right that B1, B3, B4 and B5 are one finding with four
instances, and right about why it matters: in every case the unchecked thing
is what its chapter is about. They are listed separately because the fixes are
independent, but the shape is the reason D2 belongs above where the author
ranked it.

### B1. Manifest fields recorded and never verified

**REVIEW 1.3. The most serious code finding. Needs a ruling and is not
implemented in this session for that reason.**

Fix in **code**, required before print.

`approvals`, `mapping_ids`, `design_ids` and `python_version` can each be
replaced with the string `TAMPERED` in Build 10's stored fixture and all
sixteen tests still pass. `approvals` is the field carrying Build 09's
approver identities forward, and Chapter 8's argument is that an approval is
worthless unless it is auditable.

Two designs, and they answer different questions:

- **Seal it.** Hash the manifest body and store the digest separately, the way
  `git_commit` is effectively sealed today by being checked against the tree.
  Detects an edit after the fact. Does not establish that the values were ever
  right.
- **Re-derive it.** Rebuild `approvals`, `mapping_ids` and `design_ids` from
  the trace and the inputs during replay, and fail when they disagree with the
  manifest. This verifies rather than seals, and it is what Chapter 9's
  reconstruction argument actually claims.

Re-derivation is the correct fix and it is more work, because the trace has to
carry enough to rebuild each field. Sealing alone would close the finding
while leaving the claim unsupported, which is the failure mode the author is
right to be wary of. This needs the ruling and it should get it first, because
it is the largest piece of code work on this list.

### B2. `COMPLETE` with a non-null `halt_reason`, DONE

Fix in **code**, required. Implemented this session. A run cannot both have
finished and have halted, and nothing rejected that state.

### B3. Build 09's attribution guard is uncovered

**REVIEW 3.1b.** Fix in **code**, required before print. No ruling needed.

`authorise()` refuses a write whose `model_id`, `model_version` or `run_id` is
missing. Disabling that branch entirely leaves 17 passing tests. Its sibling
`not_approved` fails a test immediately, so the shape of the missing test
already exists next to it.

Cost: one test. This is the cheapest item in group B and the author's list
omits it.

### B4. Build 05's sixth assertion is uncovered

**REVIEW 3.1c.** Fix in **code**, required before print. No ruling needed.

Five of the six assertions the book names as Table 5.2 fail a test when
neutered. `assert_deterministic` can be deleted and fifteen tests still pass.
The determinism *property* is covered by `test_transform_is_deterministic`,
which compares bytes itself, so C5.9 stands; what is uncovered is the
assertion inside the shipped pipeline, which is the part a reader copies.

Cost: one fixture whose second pass differs, or one test that drives `run`
through a non-deterministic transform. Also omitted from the author's list.

### B5. Screen independence is structural, not asserted

**REVIEW 3.1d. Needs a ruling.**

Fix in **code**, or in **book**. Required before print either way.

Independence today is guaranteed by the absence of a channel: `run_screen` has
no parameter through which screen B could receive screen A's verdicts, and
`plan_screens` refuses same-model and unacknowledged `same_agent_twice`
configurations. Nothing catches a `prompt_builder` that closed over screen A's
output, and no test states the property.

I disagree with the framing of "enforced, or soften the book", because
enforcement here is cheaper than it sounds and does not need the book to move.
A test can assert that screen B's task text is byte-identical whether screen A
has run or not, which fails the moment anything closes over A's output, and
`run_screen` can refuse a builder whose output changes between two calls on
the same record. That is enforcement, it is perhaps thirty lines, and it makes
the printed claim true rather than softening it.

I am not implementing it because the author asked for a ruling, and because
there is a design question inside it: whether the check belongs in
`run_screen` at runtime or in the test suite only.

### B6. No test pins the Chapter 12 argument

**REVIEW 3.4.** Fix in **code**, required before print. No ruling needed.

`test_shortlist_matches_known_answer` pins the top three, so a regenerated
Build 08 fixture set fails loudly. The book's *argument* would become false
silently at the same moment, because no test says anything about what came
fourth.

Fix: assert the full surviving ranking, that an antiparasitic ranks fourth of
sixteen, and that the margin to third is 0.10. Then the sentence in the book
has a gate, and a fixture regeneration that changes the ending fails a test
that names the ending.

The author's list has no code half for 3.4. I think this is the single most
valuable test in the plan: it is the only one that makes a printed argument,
rather than a printed number, fail loudly when the ground under it moves.

### B7. `ruff` is not installable from the documented install, DONE

**REVIEW 1.1.** Fix in **code**, required. Implemented this session.

### B8. The no-dash rule has no test

**REVIEW X.5.** Fix in **code**, required before print. No ruling needed.

`CLAUDE.md` describes the no-dash house rule as checked. Nothing checks it.
The one committed en dash, in `references/references_report.md:167`, is a
quoted Crossref title and is correct as it stands: altering a publisher's
registered title to satisfy a house style would be a worse defect than the
style violation.

So the test needs an exemption list, and the exemption list is the useful
part: it turns "a dash we decided to keep" into a recorded decision rather
than a thing the next session either notices or does not. Files under
`references/` that hold verbatim external records are the exemption;
everything else fails.

Cost: one test at the root. Omitted from the author's list, and it is the only
rule in `CLAUDE.md` claimed to be checked that is not.

---

## Group C: true, but the wording overstates it

None of these is required before print in the sense the others are. Each is a
sentence that would survive a hostile reading with an eyebrow raised rather
than a correction demanded.

- **C2**, C7.8: "property-matched decoys" are matched on molecular weight and
  logP. Build 08's fixture README says so; the book's phrase implies more.
  One clause in the book.
- **C3**, C4.8: the gold set is rule-defined, but its negative component is a
  caller-supplied fixed count, `GOLD_NEGATIVES`. The code's own docstring says
  so. One clause.
- **C4**, X.4: no build imports another, but Build 12 hard-codes filesystem
  paths into five build folders and Build 11 does the same. Renaming a build
  breaks both, which Part 1 demonstrated. Desirable, and the current
  arrangement is defensible: paths are not imports, and the alternative
  couples the builds harder than the paths do.
- **C5**, C7.4: `prediction_confidence` being computed over the pocket cannot
  be enforced by any caller-side code and the fixtures are fabricated. Leave
  it. It is a documented expectation and it should stay documented.
- **C6**, C3.2: the seven-step narrative is prose about a diagram. The
  verifiable half, one model call per turn, is true.

---

## Group D: desirable

- **D1. A real docking engine behind the stub.** Desirable, post-print, needs
  a ruling if it is ever to change a printed number. See A4: it does not
  substitute for the book fix and must not be allowed to delay it.
- **D2. Assertion mutation as a permanent gate.** The author ranks this
  desirable. **I would promote it to required, after B1.** REVIEW 3.1 found
  four instances of the same shape by hand, in one session, because somebody
  thought to try. Fixing B3 and B4 individually closes the two instances that
  were found. A gate that neuters each named guard and asserts a test fails is
  what stops the fifth instance from being written next month. It is also
  cheap in the form that matters: a table of guard name against the test that
  must fail, run in CI, not a general mutation framework.
- **D3. `README.md` naming `ruff` and the lint gate.** B7 makes ruff
  installable. Nothing in `README.md` tells a reader the lint gate exists, and
  `CLAUDE.md` makes it point 2 of the definition of done. One line in the
  README. Not done in this session because the task scope named
  `requirements.txt` only.

---

## Two required items with nothing to fix

Both are on the author's REQUIRED, code list. I checked each against the
repository before implementing anything, and neither exists.

### "Pandera import failing loudly rather than disabling validation"

There is no such fallback. `builds/05-wrangler/schema.py:13` imports
`pandera.pandas` at module top level and `validate.py:16` imports
`pandera.errors` at module top level. Neither is guarded. A repository-wide
search for `ImportError`, `ModuleNotFoundError` and `contextlib.suppress` in
every `.py` file outside `.venv` returns nothing at all, and no test uses
`pytest.importorskip` or a skip marker.

A missing pandera therefore raises `ModuleNotFoundError` on import of
`schema.py`, which fails `pipeline.py`, every Build 05 test, and Build 11's
wrangler worker, which reports it as `WorkerError` with the subprocess stderr
attached, `adapters.py:122`. Validation cannot vanish, because there is no
code path in which it is optional.

`pandera.errors.SchemaError` is caught in `validate.py`, and only that. It is
the schema refusing a frame, which is the point of the file.

Nothing implemented. If the author knows of a place I have not found, name it
and it will be fixed.

### "Add pandera to the README's install instructions if it is missing"

It is not missing. `README.md` gives one install instruction,
`pip install -r requirements.txt`, and `requirements.txt:21` carries
`pandera>=0.20,<1.0` with a comment explaining the floor and its interaction
with the pandas cap. The README lists no packages individually, so there is
nothing to add without changing what kind of document it is.

Nothing implemented.

---

## Where I disagree with the ranking

Six places. Four are additions, one is a promotion, one is a removal.

**1. "11 of 25" should not be corrected or removed.** The author's REQUIRED,
book list groups it with the sixty-line and one-place numbers. It does not
belong there. REVIEW 3.2 recomputed it exactly: 11 of 25 caught, 14 missed, 14
silent, and it sits in the *checkable* column alongside the 9.9x routing
saving and the plate arithmetic. It is one of the six numbers in this book a
reader can reproduce from the repository. The caveat worth printing is that it
is measured against this repository's red team suite and not against the
field, which is a clause, not a correction. Deleting a true and reproducible
number while the false ones are being fixed makes the book weaker for no gain.

**2. The Chapter 12 fix needs a code half, B6.** The author's list puts 3.4
entirely in the book. Rewriting the sentence fixes today's printing and leaves
the new sentence exactly as unpinned as the old one: nothing in the suite
speaks to why an antiparasitic missed the shortlist, so the corrected claim
can become false silently the next time Build 08's fixtures are regenerated. A
test that asserts fourth of sixteen and a 0.10 margin is the cheapest
insurance in this plan.

**3. B3 and B4 are missing from the required list and should be on it.**
Build 09's attribution guard and Build 05's sixth assertion are the other two
instances of the pattern the author has correctly identified as systematic.
Neither needs a ruling and each is one test. Leaving them out while fixing B1
closes the expensive instance and leaves the two cheap ones open, which is the
wrong way round.

**4. B8, the no-dash rule, is missing.** It is the only rule `CLAUDE.md`
describes as checked that has no check. That is the same defect class as the
book stating as achieved what was intended, in the file that tells every
future session what the standards are.

**5. D2 should be promoted from desirable to required, after B1.** Reasoning
in D2 above: the review found four instances of one shape by hand, and hand
discovery does not repeat. This is the only item on the list that prevents the
fifth instance rather than closing the fourth.

**6. On B5, screen independence, I disagree with the framing.** "Enforced, or
soften the book to say documented" presents two options where a third is
cheaper than the first and better than the second. Asserting that screen B's
task text does not vary with screen A's output is a real enforcement of the
real property, roughly thirty lines, and it leaves the printed claim true. I
would not soften Chapter 4 until that has been tried.

One more, smaller: **A2 and A3 have a code half the author's list does not
mention.** `assert control.passed` against a threshold the fixture was
constructed to clear is decoration by `CLAUDE.md`'s own definition, in the
test whose docstring quotes the chapter's strongest sentence.

I agree with everything else, and in particular with the two rulings the
author has reserved, B1 and A4. Both are cases where the plausible cheap fix
closes the finding by making it invisible: sealing a manifest without
re-deriving it, and replacing a stub with an engine nobody can run.

---

## Implemented in this session

Four items, chosen because each is wrong regardless of what the book says.

| Item | Change |
|---|---|
| B7 | `ruff` added to `requirements.txt` under a major cap |
| B2 | `RunManifest` rejects `COMPLETE` with a non-null `halt_reason` |
| C1 | `REVIEW.md` and `CLAIMS.md` committed, untouched |
| pandera | Investigated, nothing to fix, recorded above |

Nothing in groups A, C or D is touched, and B1, B5 and A4 are untouched by
design: each is waiting on a ruling where the obvious fix would close the
finding rather than answer it.

---

# Addendum, 2026-08-30

Appended rather than folded into the plan above, for the same reason the review
carries its corrections at the end: the record of what was concluded, and what
was later found wrong, is worth more than a document that has been tidied into
agreement with itself.

## Corrections

**A2, A3 and disagreement 1 rest on a false premise.** The author grepped all
fifteen manuscript files: `1.13`, `3.6` and `11 of 25` return zero hits each.
They came from earlier sessions' build reports, and the review read those as
the book. So:

- **A2 and A3 are struck as book items.** No sentence in the manuscript
  presents these stipulations as measurements, because no sentence mentions
  them. The code half stands and is now the whole of it, with no print
  deadline: a test asserting that a constructed value clears a threshold the
  construction was built to clear is decoration whatever the book says.
- **Disagreement 1 is withdrawn**, and it was arguing against a correction the
  author was never going to make. The point underneath it survives and is
  narrower than I put it: 11 of 25 is reproducible from this repository, so if
  it ever does reach a page it needs only the clause about what it was measured
  against.

**3.9 does not reproduce.** Detail in REVIEW.md's correction note. Breaking
Build 05 fails Build 12's end-to-end test in 74 seconds, naming the build. The
finding is struck; the per-build count anchor it prompted is implemented.

## Rulings received

- **B5, screen independence: book, not code.** Enforcing independence by
  construction would make the `agent_and_human` configuration impossible, since
  a human screen arrives as a file passed in, so enforcement would contradict a
  printed configuration. My disagreement 6 was wrong on this point and the
  argument that beat it is not one I had: I was reasoning about how the
  prompt builder could be constrained and not about what the configurations
  have to permit. Chapter 4's wording changes instead. Code unchanged.
- **A4, the docking control: required, and neither of my two options.** A
  recorded real run. Vina is installed once, the control is run genuinely, that
  output is committed as the fixture, and the book prints the number that run
  produced with a note that the tests replay it. CI stays offline. This is
  better than the book fix I recommended, because the printed number becomes
  true rather than merely honest about being untrue, and it does not cost
  hermeticity. Now genuinely optional, since Chapter 7 states what the
  repository does.
- **D2, assertion mutation: promoted to required, and implemented.** Below.
- **B1, manifest field verification: the hash approach is refused.** Recomputing
  the recorded hashes at replay time would replace one unverified field with
  another and make audit replay require the world it exists to survive.

## Done on the author's side

Four book corrections: the sixty-line claim in Chapter 3, the
single-configuration-file claim in Chapter 2, the independence wording in
Chapter 4, and Chapter 7 now stating that the repository replays recorded
output and proves nothing about the reader's docking setup.

## B9, new: `approval_without_identity` survives in Build 12

**Found by the mutation gate while it was being written, which is the argument
for the gate in one sentence.**

`checkpoints.py`, in `checkpoint()`, refuses an approval with no named approver
and no written reason. Neutering that branch leaves Build 12's gate at 14
passed. The comment above the tampering block in
`test_no_stage_proceeds_past_an_unapproved_checkpoint` says "an approval with
no named identity is refused too, and so is one signed over different content",
and only the content half is exercised. The prose is the coverage.

This is the fourth instance of documented-not-enforced, and the first one
found by a machine rather than by somebody thinking to try. It is recorded in
`SURVIVORS` in `tests/test_mutation_gate.py` alongside B3 and B4. Required
before print, no ruling needed, one fixture and one assertion.

## The mutation gate

`tests/test_mutation_gate.py`. Fourteen guards, each neutered in a throwaway
copy of the repository, each run against the test that should notice.
Eighteen to twenty-five seconds, four workers, one repository copy per worker.

Two properties keep it from becoming what it exists to prevent. A guard in
`CAUGHT` must fail its *named* test, not merely some test, because coverage by
accident lasts until somebody edits the accident. A guard in `SURVIVORS` must
still survive, so the list of known holes can only shrink and a hole cannot be
quietly re-admitted.

Both directions were watched failing before either was trusted: emptying
`test_row_conservation` made the gate report `row_conservation survived
mutation`, and moving a caught guard into `SURVIVORS` made the gate report that
it is now caught and the entry has to go.

Three survivors are recorded, all pre-existing, none of them fixed here:
`determinism_assertion` (B4), `machine_attribution` (B3) and
`approval_without_identity` (B9). Recording them is not blessing them. Each is
one test, none needs a ruling, and the gate now fails the day any of them is
closed without the record being updated.

## Still open

- **B1**, manifest field verification, by re-derivation. The hash approach is
  refused, above.
- **B3, B4, B9**, the three recorded survivors.
- **B6**, a test pinning Chapter 12's corrected argument.
- **B8**, the no-dash rule.
- **A4**, the recorded real docking run.
- **A7 to A9**, and the empty `MODELS.md` table.
