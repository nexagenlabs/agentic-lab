# Build 10: Run Manifest

Introduced in **Chapter 9** of *The Agentic Lab*, "Provenance: Logging, Run
Manifests, and Re-Running an Agent Six Months Later".

The collection point for every provenance fragment the previous seven builds
produced, plus the replay machinery that uses it. This is the build the
subtitle was written for: everything before it promised workflows you can
validate, and this is where a run either reproduces or does not.

## Two kinds of replay, and both are required

They answer different questions, and neither answer substitutes for the other.
Building only one is the mistake the module exists to prevent.

**`verify_replay(manifest, ...)`** re-executes the pipeline. It needs the
model, and the same version of it, and it proves that **the result still
follows from the inputs today**. It catches a model whose behaviour has moved
under you. It stops working the day the vendor retires the version you ran, and
it refuses rather than warns when the configured version differs, because a
replay against a different version is a different experiment and reporting it
as a failed reproduction sends somebody hunting for a bug in code that did not
change.

**`audit_replay(manifest, ...)`** reconstructs the run from the stored trace.
No model, no network. It proves that **the result followed from the inputs
then**, and it survives model deprecation indefinitely, which is the only
property that matters when the question arrives four years later from somebody
who was not there.

## Audit replay works because the trace stored the completions

The trace records **what the model actually said**, not only what was concluded
from it. `model_completion` events carry the raw completion text verbatim.

A trace of conclusions lets you check that somebody's summary matched their
notes. A trace of completions lets you rebuild the outputs from the model's own
words with no model present. `test_the_trace_stores_completions_not_conclusions`
asserts the distinction directly: each completion carries the model's own
`reason` and `confidence` and carries no `criteria_version`, because that is
stamped on afterwards by the pipeline. It costs more disk. Disk is the cheapest
thing in the building and a deprecated model is not purchasable at any price.

## The offline requirement is enforced, not assumed

`test_audit_replay_reproduces_outputs` cuts the network at three layers before
it replays anything: `StubModel.complete`, `httpx.Client.send`,
`httpx.Client.request`, `httpx.HTTPTransport.handle_request`,
`socket.socket.connect` and `socket.create_connection` all raise
`ModelWasCalled`.

Then, and this is the part that makes the test worth having, it **proves the
cut bites** by running `verify_replay` through it and asserting that the live
replay dies. Only then does it run the audit replay. Without that middle step
the test would pass just as happily against a patch that did nothing, and a
test that passes because nothing happened to call out has established nothing
about a machine with no key on it.

## Content addressing, not filenames

`results_final_v3.csv` tells you what somebody hoped on the afternoon they
named it. `hash_file` is applied to every input and every output, and `bytes`
is recorded beside every digest so a truncated file is visible without
rehashing four gigabytes on a laptop.

External responses are hashed too, and the bodies are kept in the trace.
`ExternalCall` records endpoint, query and `response_sha256`, and that is the
field that converts database drift from an invisible confound into four lines
in a report.

## `corpus_snapshot_id`, the field the listing does not carry

The printed listing does not have it. The chapter's failure account ends by
adding exactly this field, because a replay that disagrees has to be able to
say which version of the world it operated on.

It is a hash over the sorted input identifiers and their content hashes, and
**a fetched response counts as an input**: the endpoint and query are the
identifier, the response digest is the content. Leaving external responses out
would produce a corpus identifier that stayed constant across precisely the
drift it exists to describe. Sorted, so the order things were read in cannot
change the answer.

In the file it sits after `trace_sha256` with a comment saying it is not in the
listing, so a reader typing from the printed page gets the printed page.

## `git_dirty` is recorded, not forbidden

A run from an uncommitted tree is disclosed rather than blocked. `dirty_run`
replays successfully and the difference report lists the uncommitted changes
under CODE with the note that the commit hash does not identify the code that
ran. The commit hash alone never did, and a system that pretends otherwise is
worse than one that admits it, because it converts a known unknown into a false
certainty.

## Nothing is reproducible in the abstract

`manifest.describe()` returns the claim with its conditions filled in, and it
goes at the top of every difference report:

```
Run run-2026-02-17-a is reproducible against corpus snapshot 89a7f444...,
at commit 4f1c9ae37b62d0518c4a7e9f2b3d6084ac15e7d9 from a clean tree,
with stub-screener@2026-05-01, on Python 3.11.9. Status COMPLETE.
```

A manifest with no snapshot says `UNRECORDED` rather than reading as though it
had one.

## The difference report: which of three things moved?

A report that says "outputs differ" is the beginning of two days of work. A
report that says "four external response hashes changed and nothing else did"
is an answer.

There is a section per candidate, always, in the same order, whether or not
anything moved in it. The empty sections carry weight: "the code did not
change" is what makes "the world did" believable.

```
python replay.py fixtures/drifted_run --against fixtures/stored_run
```

```
DIFFERENCE REPORT: run-2026-02-17-a against run-2026-08-11-b
Outputs differing: 2 (outputs/summary.json, outputs/verdicts.json)

CODE: unchanged
  same commit 4f1c9ae37b62d0518c4a7e9f2b3d6084ac15e7d9, same lockfile, both trees clean

MODEL: unchanged
  same versions in both runs: stub-screener@2026-05-01

WORLD: changed
  external response hashes changed: 4
    ...?ids=REC-001,...,REC-006: 82b4ec9d9e447526 to 9f6c6447f5f61a59
    ...?ids=REC-007,...,REC-012: 23bfe7b2532a3dab to 8822aa0224eb6b08
    ...?ids=REC-013,...,REC-018: 62dc4fc905dcdfba to fe173c4a69d3adbf
    ...?ids=REC-019,...,REC-024: eb837a04b29e1641 to b7516d8954e9375d
  corpus_snapshot_id 89a7f4449852b887 to cc2135b393dff8fe

ATTRIBUTION: the world moved
This is not a failure. 4 external response hash(es) changed, the code and the
model did not change, and the difference in the outputs follows from upstream
records having been revised between the two runs. Neither run is wrong.
```

### Explained is not the same as failed

Four hashes moving and six inclusions changing is **not a failure**. Nobody was
wrong, the upstream records were revised, and both runs are correct accounts of
different worlds. Reporting that as a failure teaches people to ignore the
report.

The case that deserves alarm is the opposite one: outputs differing with
nothing moved anywhere. `difference.py` calls it `unexplained_divergence` and
says what to look for, because something that determines the result is not in
the manifest. An unrecorded seed, an unstable sort, a dictionary order, a
timestamp inside an output.

## Collected by copying, not by importing

| Fragment | From |
|---|---|
| JSONL step trace, model version, step count, stop reason | Build 01 |
| Criteria file version stamped on every verdict | Build 03 |
| Approved column mapping with unit evidence | Build 05 |
| Synergy model commitment with timestamp | Build 06 |
| Structure record, box strategy, engine version, seed | Build 08 |
| Write proposals, approvals, approver identity | Build 09 |

Record shapes are copied rather than imported. Each build stands alone, and a
manifest that imported six builds would be a manifest that only runs inside
this repository.

Nothing in this build is new, and that was deliberate. A provenance system
bolted on at the end is always incomplete in exactly the ways that matter,
because the fields you forgot are the fields nobody was recording, and no
amount of care at the end recovers them.

## Run it

```
python replay.py fixtures/stored_run
python replay.py fixtures/drifted_run --against fixtures/stored_run
python fixtures/make_fixtures.py
```

The spec offers `make replay RUN=<id>` or a `replay.py` entry point; this
repository has no Makefile anywhere and is developed on Windows, so `replay.py`
is what ships. `make replay RUN=stored_run` corresponds exactly to
`python replay.py fixtures/stored_run`.

## Tests

```
pytest builds/10-run-manifest/tests/
```

Sixteen, none of which touches the network, and one of which proves it rather
than assuming it. The six the spec names are present under those names.

## What is not here

No live model and no live database. `pipeline.py` is a screening run in the
shape of Build 03, deliberately the smallest thing that still contains all four
sources of divergence: code, model, inputs and the world.

No automatic collection of `git_commit`, `git_dirty`, the Python version or the
lock file hash from the running machine. `ManifestBuilder` takes them as
arguments. Reading them from the environment would make the fixtures depend on
the machine that generated them, which is the failure this build exists to
argue against, and a real pipeline should call `git rev-parse HEAD` and
`git status --porcelain` at the top of the run and pass the answers in.

The pipeline is not resumable. A run that halts records INCOMPLETE with a halt
reason and stops; picking up where it left off is a different chapter.
