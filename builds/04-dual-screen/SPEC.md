# SPEC: Build 04, dual-screen

**Chapter 4, "Literature Triage Agents: Screening That Survives Peer Review",
second half.**

## Purpose

Two independent screens over the same corpus, scored against each other and
against a hand-labelled gold set, producing numbers you could put in a methods
section. This is where the sixth audit question from Chapter 1, the one about
ground truth, stops being an intention and becomes a measurement.

The architecture is not invented here. It is the two-reviewer standard that
evidence synthesis already trusts, with an agent in one or both chairs.

## Relationship to Build 03

Copy Build 03's screening machinery and its fixture corpus. Do not import from
`builds/03-triage-agent/`.

The gold set here is a **subset** of Build 03's ground truth, selected the way
the chapter says to select it, which is not at random.

## Behaviour required

**Independence is structural, not asserted.** The two screens must not be able
to see each other. That means separate output files joined only at scoring
time, two differently worded prompts derived from the same criteria file, and
two distinct model identifiers. If the second screen can read the first
screen's verdicts, the build is wrong regardless of what the tests say.

Provide the three configurations from Table 4.3, and make the third refuse
without an explicit flag:

- `two_agents`, different models. The default.
- `agent_and_human`, where one screen reads verdicts from a file a human wrote.
- `same_agent_twice`, which measures inter-run stability only. Calling this
  without `acknowledge_not_a_second_reviewer=True` must raise, with a message
  saying that a model agreeing with itself tells you the temperature is low and
  nothing about whether the decisions are right.

**The gold set is enriched, not random.** It is defined by a rule, not by a
size: every inclusion, every flag, every designed case, and eight negatives
drawn with a recorded seed. The rule must be written as code, so that a later
build adding records cannot silently leave the gold set stale.

The set is a union, so a record that is both a designed case and an inclusion
appears once. On Build 03's sixty-one record corpus the rule yields
twenty-two records. That number is an output, not an input, and no code or
test may hard-code it.

The eight negatives are drawn from records that are neither inclusions, nor
flags, nor designed cases, and the seed is recorded in the output. A gold set
that cannot be reconstructed is not a reference standard.

A random twenty from a low-prevalence corpus contains no positives and
measures nothing, and the code should make that impossible rather than leaving
it to the reader.

**Metrics.** Compute and report, in this order:

1. Sensitivity, first, because it is the only number that says what you lost.
2. Specificity.
3. Negative predictive value.
4. Observed agreement between the two screens.
5. Cohen's kappa, with the Landis and Koch band named.
6. A prevalence-adjusted statistic. Implement both PABAK and Gwet's AC1, and
   report both alongside kappa.
7. Positive predictive value, last, and expect it to be low.

**Accuracy is not computed and not reported.** If a caller asks for it, raise
with a message explaining that at this prevalence a screen excluding every
record scores above ninety per cent. This is a design decision the chapter
argues for at length and the code should enforce it rather than merely omit it.

**Adjudication.** Records where the two screens disagree go to an adjudication
file, with both verdicts and both reasons side by side. Nothing resolves a
disagreement automatically. The output states how many records went to human
adjudication, because that number is the real cost of the screen.

## The report template

Emit `screen_report.md` from a template, filled with: corpus size, criteria
version, the two model identifiers, gold set size and how it was selected,
sensitivity, specificity, NPV, PPV, observed agreement, kappa with its band,
PABAK, AC1, the count sent to adjudication, and the run identifier.

The gold set composition is itemised rather than summarised: how many
inclusions, how many flags, how many designed cases, how many seeded
negatives, and the seed. A reader must be able to see that the set was
enriched deliberately rather than sampled, because that difference is the
whole reason it can measure anything.

It must be pasteable into a methods section without editing. If a reader has to
rewrite it, the template is wrong.

## Fixtures

Reuse Build 03 fixture corpus in full. Add:

- `fixtures/screen_a.json` and `fixtures/screen_b.json`, two sets of verdicts
  over the same corpus, constructed so the agreement statistics are worth
  computing. Design them so that observed agreement is high while kappa is only
  moderate, which is the prevalence artefact the chapter describes. Record in a
  comment what kappa and AC1 they are constructed to produce, so a test can
  assert against a known value rather than against whatever the code happens to
  return.
- `fixtures/disagreements_expected.json`, the records the two screens differ
  on, for the adjudication test.

## Gate: `pytest builds/04-dual-screen/tests/`

**`test_sensitivity_above_threshold`**
Score screen A against the gold set. Assert sensitivity clears a threshold read
from configuration, and assert the threshold was set before the result was
computed, by requiring it as an input rather than a default.

**`test_agreement_reported`**
Assert observed agreement, kappa, PABAK and AC1 are all present in the run
manifest and in `screen_report.md`, and that kappa carries its Landis and Koch
band as a word, not just a number.

**`test_criteria_version_matches`**
Assert every verdict in both screens carries the same `criteria_version` and
that it matches the criteria file on disk. Assert that scoring two screens with
different criteria versions raises rather than proceeding.

**`test_accuracy_is_refused`**
Assert that requesting accuracy raises, and that the message explains why.

**`test_same_agent_twice_requires_acknowledgement`**
Assert the third configuration raises without the explicit flag.

**`test_kappa_matches_known_value`**
Compute kappa, PABAK and AC1 on the constructed fixtures and assert they match
the values recorded in the fixture comment, to three decimal places. This is
the check that your statistics are right rather than merely present.

**`test_disagreements_go_to_adjudication`**
Assert every record where the screens differ appears in the adjudication file
with both verdicts and both reasons, and that none was resolved automatically.

No test may touch the network.

## Out of scope

No full-text retrieval. No PRISMA diagram. The corpus is the fixture corpus from
Build 03.

## Report back

Against the five points in `CLAUDE.md`, plus the actual sensitivity,
specificity, kappa, PABAK and AC1 your fixtures produce, and the count sent to
adjudication. If kappa and observed agreement diverge, say so, because that
divergence is the chapter's point.
