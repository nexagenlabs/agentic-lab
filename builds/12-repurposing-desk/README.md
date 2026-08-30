# Build 12: Repurposing Desk

Introduced in **Chapter 12** of *The Agentic Lab*, "The Integrated Repurposing
Desk: Cost, Latency, Judgement, and the Limits".

The last build. It connects the eleven before it into a system that takes a
repurposing question from literature to a ranked shortlist, with a provenance
trail behind every step and three human checkpoints along the way.

It does not answer the question. That is not a limitation being apologised for;
it is what the chapter says the honest version of this system looks like.

## What no gate could catch

The fixture question asks which approved **antiparasitic** agents show activity
against PKC isoforms. The corpus the desk retrieves from is Build 03's, which
is a **hepatotoxicity** corpus. This is the shortlist:

| # | Compound | Score | Evidence |
|---|---|---|---|
| 1 | clozapine | -9.6 | PMID 99000005 |
| 2 | chlorpromazine | -9.3 | PMID 99000005 |
| 3 | diclofenac | -9.1 | PMID 99000007 |

**None of the three is an antiparasitic.** Ivermectin appears in the corpus
exactly once, in a record screening correctly excluded because the assay was in
HEK293 cells, which is not a liver model.

And everything worked.

- **Every stage did its job.** Retrieval returned the corpus it was pointed at
  and deduplicated it. Screening applied criteria version 3 and agreed with
  Build 03's hand labels on 57 of 61 records. Triage resolved three flags in a
  bounded loop. Structure acquisition checked provenance. Docking parsed real
  recorded engine output. Ranking sorted by top score and refused nothing,
  because there was nothing to refuse.
- **Every test passed.** All 245 in the repository, including the eleven prior
  builds' gates run in sequence against this desk.
- **The run replays byte for byte.** Offline, with the model client, three
  `httpx` methods and two `socket` entry points patched to raise, and the patch
  proven to bite first.
- **The provenance is complete.** Three checkpoints blocked, three named
  approvals were recorded, every input and output is content-addressed and the
  corpus snapshot identifier is in the manifest.

The answer is to a different question from the one that was asked, and nothing
in the pipeline is capable of noticing, because **no stage owns the
relationship between the question and the corpus**. Retrieval is not asked
whether the corpus suits the question; it is asked for the corpus. Screening is
not asked whether the criteria address the question; it is asked to apply the
criteria. Ranking is not asked what the shortlist is for. Every stage has a
narrow, checkable contract, every contract is honoured, and the composition of
twelve honoured contracts is wrong.

This is the argument for `test_all_prior_gates_pass_in_sequence` stated as a
result rather than as a principle. A system whose components each pass and
which has never been tested end to end has not been tested. What running it end
to end found was not a broken component. It was that the thing the components
add up to was never specified anywhere, so nothing could check it.

**The fix is not code.** It is somebody at the screening checkpoint noticing
that twelve inclusions about paracetamol and amiodarone are not evidence about
ivermectin, and stopping the run. That checkpoint exists, it blocked, and it
recorded an approval saying the reviewer was content. I wrote that approval.
Which is the second finding, and the one that should worry a reader more than
the first: **a checkpoint is only as good as the person at it**, and this
repository can prove that a checkpoint blocked, that an approval was named and
that it was bound to a hash of exactly what was shown, and it cannot prove that
anybody looked.

## Only three stages are agent loops

Table 12.1 lives in `stages.py` as data, not in this README as prose, because
`test_only_three_stages_are_agent_loops` walks it.

| Stage | Level |
|---|---|
| Corpus retrieval and deduplication | script |
| Abstract screening against criteria | chain, one model call per record |
| **Full-text triage of ambiguous records** | **agent loop** |
| **Instrument export mapping** | **agent once, script thereafter** |
| Transformation, units, assertions | script |
| Structure acquisition and preparation | chain |
| Docking execution and parsing | script |
| Ranking and shortlist assembly | script with a gate |
| **Protocol adaptation** | **agent loop** |

The test asserts three, and it does not take the table's word for it. A chain
makes one model call per item however many items it has; a loop calls again
about the same item, having read what came back the first time. `StageCost`
records `max_calls_per_item`, so the distinction is measured. Screening makes
**61** model calls with a maximum of **1** per record and is a chain. Triage
makes 9 across 3 records and is a loop.

The printed spine runs two of the three. Export mapping is the third and runs
once per instrument, then replays an approved mapping with no model call at
all, which is Build 05's whole argument.

`desk.py` is one orchestrating function calling deterministic stages. The test
asserts that on the syntax tree rather than by grepping for words: `run_desk`
contains no `if`, no `for`, no `while` and no `try`, so there is nowhere for a
planner to live. One study measured multi-agent systems at four to two hundred
and twenty times the tokens of single-agent equivalents, and a rebuild found
eighty per cent of a five-agent system's tokens going on agents describing
their work to each other.

## The three checkpoints are the spine

Each blocks, each writes a named approval into the manifest, each sits
immediately before an irreversible narrowing.

| Checkpoint | Declared minutes | What it gates |
|---|---|---|
| screening | 45 | the corpus is cut to what will be read in full |
| targets | 45 | compute is committed to a target and a box |
| shortlist | 90 | a candidate goes to a bench |

An approval is bound to a hash of what was approved. If a stage upstream
changes and the artefact is no longer the one that was signed, the checkpoint
refuses with `approval_is_for_different_content`. An approval that survives a
change to the thing it approved is not a record of anybody's judgement, it is a
token that accumulated authority by sitting in a directory. The cost is that
the committed approvals must be regenerated when a stage changes what it
produces, which is what `fixtures/make_checkpoints.py` is for.

`test_no_stage_proceeds_past_an_unapproved_checkpoint` proves the prohibition
bites before asserting the approved path works: for each checkpoint in turn it
removes the approval, asserts the run halts there, and asserts that every
downstream stage recorded nothing. Asserting only that the approved path works
would pass against a checkpoint that did nothing at all.

## Cost, measured and declared, kept apart

`run_accounting.md` is emitted per run in the shape of Table 12.2.

```
| Stage                | Level                             | Human (declared) | Calls | Tokens         | Cost | Seconds |
| abstract_screening   | chain, one model call per record  | **45 min**       | 61    | cheap 2470     | 2.47 | 0.0305  |
| full_text_triage     | agent loop                        | -                | 9     | workhorse 270  | 1.35 | 0.0049  |
| structure_acquisition| chain                             | **45 min**       | 0     | -              | -    | 0.0009  |
| docking              | script                            | -                | 0     | -              | -    | 0.0080  |
| protocol_adaptation  | agent loop                        | **90 min**       | 2     | frontier 138   | 3.45 | 0.0015  |
```

**Measured compute:** 72 model calls, 2878 tokens, 7.27 relative cost units,
0.046 seconds of wall clock.
**Declared human attention:** 180 minutes across three checkpoints.

The two are reported separately and never added, because minutes and tokens do
not add.

Two honesty notes are printed in the file itself. The human minutes are
**declared**, not measured: nothing can time how long somebody spent looking at
a diff. And the wall clock is this run on this machine with recorded fixtures
standing in for a docking engine and a model API, so it is a twentieth of a
second rather than the chapter's forty minutes. Printing forty minutes here
would be an estimate wearing a measurement's clothes.

The ninety minutes at the shortlist is the largest single block of human time
in the run, equal to the other two checkpoints put together, and nothing in
this repository automates any of it.

## Routing is real, and the extra spend buys nothing

Three tiers: cheap for per-record screening, workhorse for the agent loops,
frontier reserved for protocol adaptation, where being wrong is expensive and
the volume is one.

```
routed:        7.27 relative cost units
--all-frontier: 71.95
ratio:          9.9x
```

Almost exactly an order of magnitude, which is the chapter's claim. The second
half of the test matters more: **the shortlist is identical**. Same three
compounds, same scores, same protocol. `TieredClient` makes the completion a
function of the payload and never of the tier, precisely so that this
comparison measures one thing.

## The whole run replays offline

`test_full_run_replays_from_manifest` cuts the network at six entry points
(`TieredClient.complete`, three `httpx` methods, two `socket` ones), proves the
cut bites by running a live desk through it and watching it die, and only then
replays. Every output hash matches, and zero model calls are made.

There is no replay-specific code inside `run_desk`. Every model call goes
through `stages.ask`, so audit replay is `run_desk` again with a `ReplayClient`
serving the recorded completions. That has a property worth more than the
offline guarantee: `ReplayClient` refuses if the stage asking for completion
*n* is not the stage that produced it, so a replay that reproduces the outputs
has reproduced the path, not arrived at the same answer by another road.

## The shortlist matched the hand-produced one

It did, exactly: clozapine, chlorpromazine, diclofenac, in that order, with
those scores.

**That is consistency, not validation, and it is worth being precise about
which.** The known answer was derived from Build 03's committed `gold.json`
labels, which were hand-written for Build 03 and which this build did not
produce, so the survivor set is genuinely independent of this desk's screening
stub. The docking scores come from Build 08's generator. The ligand mapping is
alphabetical and was fixed in the question before any score was looked at.

So the agreement establishes something real: the desk's screening matches
Build 03's hand labels on every record that decides the top three, and the
compound-to-ligand mapping, the pdbqt parsing and the ranking arithmetic are
all correct. That is the plumbing, and the plumbing is worth checking.

It establishes nothing about the science. The corpus, the gold labels, the
docking scores and the known answer all came out of the same project, and
agreement across artefacts with a shared origin is a weaker claim than it
looks. The shortlist is three compounds nobody has any reason to think are
worth a bench.

## What this system does not do

Table 12.3, as six functions that raise rather than six absences. Grep for
`NotThisSystem`.

`generate_hypothesis`, `is_promising`, `predicted_affinity`, `novel_claim`,
`decide`, `rank_by_confidence`.

A module with no `generate_hypothesis` is an invitation to write one: the
absence looks like an oversight, the name looks obvious, and the person adding
it has no idea there was an argument. A module that exports it and raises with
three sentences saying why is a conversation with that person at the moment
they need it. Build 04's `accuracy` and Build 08's `predicted_kd` are the same
move.

## Run it

```python
from pathlib import Path

import accounting
import desk
from provenance import RunManifest
from stub_client import TieredClient

manifest = RunManifest(
    run_id="desk-001",
    root=Path("../.."),                       # the repository root
    client=TieredClient(),                    # or TieredClient(all_frontier=True)
    approvals_dir=Path("fixtures/checkpoints"),
    workspace=Path("runs/desk-001"),
)
shortlist = desk.run(desk.load_question(), manifest)

print(shortlist.compounds())
print(accounting.write(manifest))
```

`python fixtures/make_checkpoints.py` regenerates the recorded approvals after
a stage changes what it produces.

The model names come from `config.py` and the environment: `AGENT_MODEL_CHEAP`,
`AGENT_MODEL`, `AGENT_MODEL_FRONTIER`. There is no live client anywhere in the
build.

## Tests

```
pytest builds/12-repurposing-desk/tests/
```

Fifteen, none of which touches the network. The seven the spec names are present
under those names. `test_all_prior_gates_pass_in_sequence` runs the other
eleven builds' gates in one subprocess and takes most of the running time; it
is the only test in the repository that asserts the whole thing works at once.

## The question no test can answer

Every gate in this repository can pass and the work can still have been
pointless. The chapter ends with a question no framework settles, and it is put
here rather than in a test because a test that could answer it would be lying.

**Having seen this output first, would you have acted differently?**

Not: is the shortlist plausible, is the manifest complete, did the checkpoints
block. Those are answered, and answering them took twelve builds. The question
is whether the three hours of your attention that this run consumed bought a
decision you would not otherwise have made, or whether it produced a
well-provenanced confirmation of what you were going to do anyway.

If the answer is no, the desk is an expensive way to feel rigorous, and that is
worth finding out early. Nothing in this repository can tell you. Answer it for
yourself, on your own question, before you build one of these.

## What is not here

No live ELN, no live PubMed, no live docking engine, no live model. Every
external dependency is a recorded fixture from an earlier build, because a test
that needs a network is a test that gets deleted.

No resumability. A run that halts at a checkpoint halts; picking up where it
left off is a different chapter.

No transformation stage in the spine. Table 12.1 names it and `stages.py`
declares it, but the printed `run_desk` goes from literature to docking without
an instrument export in the middle, so `map_export` and the transformation
stage exist and the spine does not call them. That is the listing's shape, not
an omission from it.
