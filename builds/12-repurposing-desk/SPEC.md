# SPEC: Build 12, repurposing-desk

**Chapter 12, "The Integrated Repurposing Desk: Cost, Latency, Judgement, and
the Limits".**

## Purpose

The last build. Connect the eleven previous ones into a system that takes a
repurposing question from literature to a ranked shortlist, with a provenance
trail behind every step and three human checkpoints along the way.

The chapter's honest accounting is the point of the build, not the pipeline.
Forty minutes of compute, three hours of attention, and a shortlist worth
taking to a bench. It does not answer the question.

## Files and printed listings

| Listing | File |
|---|---|
| `01_desk_structure` | `desk.py` |

`mode: exact`. The listing is marked "structure only", so `desk.py` must
contain that block verbatim while carrying the real implementation around it.

## The architecture the chapter argues for

Read Table 12.1 before writing anything. **Only three stages are agent loops.**
Everything else is a chain or a script, and that is the design that survived
rather than a compromise.

| Stage | Level |
|---|---|
| Corpus retrieval and deduplication | script |
| Abstract screening against criteria | chain, one model call per record |
| Full-text triage of ambiguous records | agent loop |
| Instrument export mapping | agent once, script thereafter |
| Transformation, units, assertions | script |
| Structure acquisition and preparation | chain |
| Docking execution and parsing | script |
| Ranking and shortlist assembly | script with a gate |
| Protocol adaptation | agent loop |

If your implementation ends up with more than three agent loops, stop and say
so. The reader is meant to count them.

**Do not build a coordinator delegating to specialist agents.** The chapter
reports one study measuring multi-agent systems at four to two hundred and
twenty times the tokens of single-agent equivalents, and a rebuild where eighty
per cent of a five-agent system's tokens went on agents describing their work
to each other. One orchestrating function calling deterministic stages is the
shape that survived.

## Behaviour required

**The three checkpoints are the spine.** Each blocks, each writes a named
approval into the manifest, and each sits immediately before an irreversible
narrowing. Nothing downstream of an unapproved checkpoint may execute. Reuse
Build 09's approval machinery.

**The manifest spans the whole run.** One `RunManifest` from Build 10 collects
every stage's fragments. `audit_replay` must reproduce a complete desk run
offline, with the model client and HTTP transport patched to raise, and with
the patch proven to bite before the replay runs.

**Cost accounting is measured, not estimated.** Record per stage: wall clock,
tokens by model tier, and a marker where human attention is required. Emit
`run_accounting.md` in the shape of Table 12.2. The chapter reports that the
largest block of human time is the ninety minutes spent looking at the
shortlist, which nothing automates, and the accounting should make that visible
rather than hiding it among the compute.

**Model routing is real.** Three tiers across the run: cheap for per-record
screening, workhorse for the agent loops, frontier reserved for protocol
adaptation. Provide `--all-frontier` and assert in a test that it costs roughly
an order of magnitude more, since that is the chapter's claim and it should be
demonstrable rather than asserted.

**What the desk does not do.** Implement Table 12.3 as refusals rather than
omissions, following Build 04's `accuracy` and Build 08's affinity precedent.
Any method that would generate a hypothesis, declare a shortlist interesting,
convert a docking score to an affinity, or make a novel claim must raise with a
message saying why. A reader should be able to find these by grepping for
`NotThisSystem` or similar.

## Fixtures

Reuse the earlier builds' fixtures rather than inventing new ones. The desk run
uses Build 03's corpus, Build 06's design, Build 08's structures and decoys, and
Build 09's notebook. Add only:

- `fixtures/question.yaml`, the ivermectin and PKC question as a `Question`.
- `fixtures/checkpoints/`, recorded approvals so the tests can run unattended.
- `fixtures/known_answer/`, a shortlist produced by hand, for the final test.

## Gate: `pytest builds/12-repurposing-desk/tests/`

**`test_all_prior_gates_pass_in_sequence`**
Run the gates from Builds 01 through 11 against the assembled desk on the
fixture question. Assert every one passes and that a single manifest records
all of them. A system whose components each pass but which has never been
tested end to end has not been tested.

**`test_no_stage_proceeds_past_an_unapproved_checkpoint`**
Assert the desk halts at each of the three checkpoints, and that no downstream
stage executes without a recorded approval carrying a named identity. Prove the
prohibition bites: run with an approval removed and assert the downstream stage
did not execute, before asserting the approved path works.

**`test_full_run_replays_from_manifest`**
Audit replay of a complete run with model and network access patched to raise,
the patch proven to bite first. Every output hash must match. This is the
book's subtitle expressed as an assertion.

**`test_only_three_stages_are_agent_loops`**
Walk the pipeline and assert exactly three stages invoke a model loop. If a
later change adds a fourth, this fails, which is the point.

**`test_routing_costs_less_than_all_frontier`**
Assert the routed run's token cost is roughly an order of magnitude below
`--all-frontier`, and that the shortlist is unchanged between them. The second
half matters more: the chapter claims the extra spend buys nothing.

**`test_refusals_are_refusals`**
Assert each Table 12.3 method raises with an explanatory message.

**`test_shortlist_matches_known_answer`**
Run the desk on the fixture question and compare against the hand-produced
shortlist. **This test may legitimately fail**, and if it does, report the
difference rather than adjusting the known answer to match. A disagreement
between the desk and a hand-produced shortlist is a finding, not a bug.

## The question no test can answer

The chapter's gate ends with a question no framework can settle: would you have
acted differently having seen this output first? Put it in the README as a
paragraph the reader is asked to answer for themselves, not as a test.

## Report back

Against the five points in `CLAUDE.md`, plus the full `run_accounting.md`, the
count of agent loops, the routed and all-frontier token costs, and whether the
shortlist matched the hand-produced one. If it did match, say whether that is
validation or merely consistency, given the criteria and the fixtures were
written by the same process that produced the shortlist.
