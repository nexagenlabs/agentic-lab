# Build 04: Dual Screen

Introduced in Chapter 4 of *The Agentic Lab*, "Literature Triage Agents:
Screening That Survives Peer Review", second half.

## Why this build has no listing

Chapter 4 prints three code listings and all three belong to Build 03. Nothing
in this build appears verbatim on a printed page, so
`tests/test_listings.py` has no entry for it and the fourth point in the
project's definition of done is vacant here rather than unmet. What this build
does is described below rather than pinned to a page.

## What this build does

Build 03 produced one set of verdicts. This one runs **two** screens over the
same corpus, scores them against each other and against a hand-labelled gold
set, and emits numbers you could put in a methods section.

The architecture is not invented here. It is the two-reviewer standard that
evidence synthesis already trusts, with an agent in one or both chairs.

## Independence is structural, not asserted

A docstring promising that two screens are independent is worth nothing. Three
things make it true here, and a test asserts the first of them:

- `run_screen` has no parameter through which another screen's verdicts could
  arrive. `test_the_two_screens_cannot_see_each_other` inspects the signature,
  so adding one breaks the build and somebody has to justify it.
- Each screen writes its own file. They meet for the first time in
  `load_screen`, at scoring time, after both are finished.
- The prompts differ in method and the models differ in name. Screen A works
  forwards through the criteria; Screen B starts at the exclusions and asks
  what would have to be true for the record to survive. Both quote the same
  criteria file verbatim, because two screens judging different rules are not
  two screens, and two identical prompts are one instrument read twice.

## The three configurations

| Mode | What it measures |
| --- | --- |
| `two_agents` | Agreement between two different models. The default. |
| `agent_and_human` | An agent against verdicts a person wrote. |
| `same_agent_twice` | Inter-run stability, and nothing else. |

`plan_screens` refuses rather than warns. `same_agent_twice` raises without
`acknowledge_not_a_second_reviewer=True`, because a model agreeing with itself
tells you the temperature is low and tells you nothing about whether the
decisions are right. `two_agents` given the same model twice also raises: that
is `same_agent_twice` wearing another name.

## The gold set is a rule, not a number

Every inclusion, every flag, every designed case, and eight negatives drawn
from the records those categories did not take, with a recorded seed.

On the sixty-one record corpus that yields twenty-two. **Nothing in the code
or the tests asserts twenty-two.** Every expectation is derived from the ground
truth file, so a later build adding records grows the gold set instead of
quietly leaving a reference standard that no longer covers the corpus it
claims to measure.

The set is a union. `99000002` and `99000061` are designed cases and also
inclusions, so they appear once, and `composition()` reports the overlap
explicitly so the itemised counts can be seen not to sum rather than be
suspected of it.

The seed is a required argument, never a default. A caller that has to pass it
is a caller that has it to record, and a gold set that cannot be reconstructed
is not a reference standard.

## Metrics, in the chapter's order

Sensitivity first, because it is the only number that says what you lost.
Positive predictive value last, because it is the number most likely to be
quoted and least likely to mean what the reader thinks. Between them:
specificity, negative predictive value, observed agreement, Cohen's kappa with
its Landis and Koch word, and two prevalence-adjusted statistics, PABAK and
Gwet's AC1.

**Accuracy is refused.** `metrics.accuracy` exists only to raise and explain:
at this prevalence a screen that excluded every record without reading any of
them would score above eighty-five per cent, so the number rewards doing
nothing. Omitting it silently would invite a reviewer to ask for it.

Two judgements the spec left open, both documented in `metrics.py`:

- **A flagged record is not lost.** A flag sends the record to a person, which
  is where a record the abstract cannot settle is supposed to go, so only an
  exclusion can lose a true inclusion. Counting a flag as a miss would punish
  the screen for the one behaviour the criteria demand of it.
- **Agreement is computed over all three decisions**, not a collapsed pair. A
  record one screen includes and the other flags is a real disagreement, and
  collapsing it would flatter the statistic.

## What the fixtures are built to show

`fixtures/screen_a.json` and `screen_b.json` are constructed backwards from a
chosen contingency table, recorded in `fixtures/agreement_expected.json`, so
the statistics are known before the code computes them.

| Statistic | Value |
| --- | --- |
| Observed agreement | 0.836 |
| Cohen's kappa | 0.472 (moderate) |
| PABAK | 0.754 |
| Gwet's AC1 | 0.806 |

That divergence is the whole point. The screens agree on eighty-four per cent
of records, which sounds strong, and kappa calls it moderate, because at this
prevalence almost all of that agreement is agreement about exclusions and
kappa charges nearly all of it to chance. Reporting any one of the four alone
invites a reader to believe it.

## Adjudication resolves nothing

Ten records differ. They go to `adjudication.json` with both verdicts and both
reasons side by side, and none is resolved automatically: no tie-break, no
confidence comparison, no third screen brought in to break the deadlock. Each
of those would turn a disagreement into a verdict nobody made.

The count is stated in the report because it is the real cost of the screen. A
pair of screens sending four hundred records to adjudication has saved nobody
anything, and that should be visible on the day rather than three weeks later.

## Run it

```
pytest builds/04-dual-screen/tests/
```

No API key, no network. The two screens are committed fixtures.

To score a run of your own, from inside `builds/04-dual-screen/`:

```python
from config import GOLD_NEGATIVES, GOLD_SEED, SCREEN_A_MODEL, SCREEN_B_MODEL
from criteria import load_criteria
from goldset import build_gold_set, load_gold
from scoring import score_run
from screens import plan_screens

criteria = load_criteria("criteria/repurposing_v3.yaml")
gold = build_gold_set(load_gold("fixtures/gold.json"),
                      seed=GOLD_SEED, negatives=GOLD_NEGATIVES)
plan = plan_screens("two_agents", model_a=SCREEN_A_MODEL, model_b=SCREEN_B_MODEL)

score_run("fixtures/screen_a.json", "fixtures/screen_b.json", gold,
          sensitivity_threshold=0.85, plan=plan,
          criteria_version=criteria.version,
          criteria_file="criteria/repurposing_v3.yaml",
          run_id="run0001", out_dir="out")
```

That writes `run_manifest.json`, `adjudication.json` and `screen_report.md`.
The threshold is required rather than defaulted, so it cannot be chosen after
the result is known.

## Layout

| File | What it holds |
| --- | --- |
| `goldset.py` | The gold set rule, and the record of how it was drawn. |
| `screens.py` | The three configurations, and the two screens that cannot see each other. |
| `prompts.py` | Two prompts, one criteria file. |
| `metrics.py` | The statistics, and the refusal of accuracy. |
| `adjudicate.py` | Disagreements, laid out for a person. Resolves nothing. |
| `report.py` | The methods-section template. |
| `scoring.py` | Where the two screens finally meet. |

`criteria.py`, `models.py`, `agent.py`, `dispatch.py`, `cache.py`,
`eutils.py`, `tracing.py` and the fixture corpus are copied from Build 03.
Nothing here imports from `builds/03-triage-agent/`: each build stands alone.

## What is not here

No full-text retrieval and no PRISMA diagram. The corpus is Build 03's.
