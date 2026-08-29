# SPEC: Build 03, triage-agent

**Chapter 4, "Literature Triage Agents: Screening That Survives Peer Review".**

## Purpose

A screening agent that judges each record against written criteria and records
a verdict with a reason. This is the first build that does real research work,
and the first whose output someone might put in a methods section.

The chapter's argument is that the hardest part of automated screening is not
the agent but writing down criteria you believed you already had. The build
reflects that: the criteria are versioned data, and the code refuses to run
without them.

## Relationship to earlier builds

Copy the loop and the typed dispatch from Build 02 rather than importing them.
Each build stands alone.

`_pubmed_esearch` was a stub in Builds 01 and 02. **Implement it properly here**,
against NCBI E-utilities, and implement `fetch_abstract` alongside it. Both go
through a cache layer so that a re-run does not re-fetch, and so the tests can
run entirely from cached fixtures with no network.

## Files and printed listings

Three listings are printed and each must appear verbatim in the file named.

| Listing | File |
|---|---|
| `01_criteria_file` | `criteria/repurposing_v3.yaml` |
| `02_verdict_model` | `models.py` |
| `03_per_record_driver` | `screen.py` |

The criteria file is printed in full, including the inline comment on
`on_ambiguity`. Reproduce it exactly.

## Behaviour required

**Criteria loading.** Criteria are read from a YAML file and validated into a
typed object. A criteria file that fails validation halts the run; it does not
fall back to a default. The `version` field is mandatory.

**One record per model call.** The loop is driven by your list of identifiers,
as printed in `screen.py`. `max_steps=4` is enough: the agent is judging a
record it already has, not going looking for one.

**The verdict is typed.** `Verdict` as printed. Note two fields that carry more
weight than they look:

- `criteria_failed` names which rule caused an exclusion, so that forty
  exclusions citing one criterion is a diagnosis rather than a mystery.
- `criteria_version` is stamped on every verdict. A run screened under
  version 2 must never be silently compared with one screened under version 3.

**Ambiguity is flagged, never guessed.** The criteria file says
`on_ambiguity: flag`. If the model cannot evaluate a criterion from the text
provided, the verdict is `flag` with `confidence: low`. The prompt must say so
explicitly, and must tell the model the asymmetry: a flagged record costs a
human thirty seconds, a wrong verdict costs a paper.

**Totals are computed in Python.** The assertion at the end of `screen_corpus`
is not decoration. The agent is never asked how many records it screened.

**Caching.** `fetch_abstract` writes each retrieved record to
`cache/<pmid>.json` with the payload and a SHA-256 of it. On a second run it
reads from cache. This is the first appearance of the content hashing that
Chapter 9 builds into the run manifest, and it is what lets the tests run
offline.

## Fixtures

`fixtures/corpus/` holds **sixty cached records** as JSON, in the shape
`fetch_abstract` returns. They must be realistic enough to screen:

- **Eight true inclusions**, reporting a numeric IC50, EC50 or percentage
  viability in HepG2, Huh7, HepaRG or primary human hepatocytes.
- **Two designed near-misses** that a careless screen gets wrong: one using
  HEK293 transfected with a liver transporter, which the criteria explicitly
  exclude, and one on primary human hepatocytes, which the criteria explicitly
  include. These two exist because they are the exact cases the chapter's
  introduction describes getting wrong.
- **Two that should flag**: a record reporting an IC50 without naming the cell
  line, and a record whose abstract is a single sentence.
- **The remaining forty-eight** are plausible negatives: reviews, non-liver
  models, papers with no drug treatment, and papers with no numeric endpoint.

Prevalence is therefore about thirteen per cent, which is higher than a real
corpus but low enough that the metrics behave the way the chapter says they do.

`fixtures/gold.json` holds the ground truth for all sixty, as
`{pmid: "include" | "exclude" | "flag"}`, with a short note on each of the four
designed cases saying why it is what it is.

Write these records yourself. Do not use real PMIDs or real abstract text.

## Gate: `pytest builds/03-triage-agent/tests/`

**`test_every_record_is_accounted_for`**
Screen the sixty-record fixture corpus with a stub that fails on three specific
records. Assert `len(verdicts) + len(failed) == 60` exactly, and that the three
failures are named in the trace. A missing record must be a logged gap.

**`test_criteria_version_on_every_verdict`**
Assert every verdict carries the same `criteria_version`, and that it equals
the `version` field in the criteria file on disk.

**`test_ambiguous_records_flag_rather_than_guess`**
Screen the two designed flag cases. Assert both return `decision: "flag"` with
`confidence: "low"`, and that neither returns include or exclude.

**`test_criteria_file_must_validate`**
Load a deliberately broken criteria file, one missing `version` and one with an
unknown key. Assert the run halts with a clear error and does not fall back to
a default.

**`test_cache_prevents_refetch`**
Fetch a record twice with a stub that counts calls. Assert the second read
comes from cache and the counter did not increase.

No test may touch the network.

## Out of scope

Two independent screens, agreement statistics and adjudication are Build 04.
This build produces one set of verdicts.

## Report back

Against the five points in `CLAUDE.md`, plus the prevalence of your fixture
corpus and confirmation that the four designed cases behave as intended.
