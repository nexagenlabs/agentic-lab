# SPEC: Build 10, run-manifest

**Chapter 9, "Provenance: Logging, Run Manifests, and Re-Running an Agent Six
Months Later".**

## Purpose

The collection point for every provenance fragment the previous seven builds
have produced, plus the replay machinery that uses it.

This is the build the book's subtitle was written for. Everything before it
promised workflows you can validate; this one is where a run either reproduces
or does not.

## Files and printed listings

| Listing | File |
|---|---|
| `01_run_manifest` | `models.py` |
| `02_hash_file` | `hashing.py` |

Both `mode: exact`.

## Collecting what already exists

Nothing here is new, which was deliberate. A provenance system bolted on at the
end is always incomplete in the ways that matter. Collect from the earlier
builds by copying their record shapes, not by importing:

| Fragment | From |
|---|---|
| JSONL step trace, model version, step count, stop reason | Build 01 |
| Criteria file version stamped on every verdict | Build 03 |
| Approved column mapping with unit evidence | Build 05 |
| Synergy model commitment with timestamp | Build 06 |
| Structure record, box strategy, engine version, seed | Build 08 |
| Write proposals, approvals, approver identity | Build 09 |

## Behaviour required

**Two kinds of replay, and both are required.** This is the idea the chapter
turns on, so implement them as clearly separate entry points.

`verify_replay(manifest)` re-executes the pipeline. It needs the model and the
same version, and it proves the result still follows from the inputs today.

`audit_replay(manifest)` reconstructs the run from the stored trace, calling no
model and touching no network. It proves the result followed from the inputs
then, and it survives model deprecation indefinitely.

Audit replay works only because you stored the completions rather than just the
conclusions. Make that explicit: the trace records what the model actually
said, not only what was concluded from it.

**Content addressing, not filenames.** `hash_file` as printed, applied to every
input and every output. A filename is a label somebody chose; a hash is an
identity. Record `bytes` alongside the digest so a truncated file is visible
without rehashing.

**Hash external responses too.** `ExternalCall` records endpoint, query and
`response_sha256`. This is what converts database drift from an invisible
confound into a detectable event, and it is what makes the chapter's failure
account interpretable.

**`git_dirty` is recorded, not forbidden.** A run from an uncommitted tree is
disclosed rather than blocked. The commit hash alone does not identify the code
that ran, and pretending otherwise is worse than admitting it.

**The corpus snapshot.** Add `corpus_snapshot_id` to the manifest, which the
printed listing does not carry. The chapter's failure account ends by adding
exactly this field, because a replay that disagrees needs to say which version
of the world it operated on. Record it as a hash over the sorted set of input
identifiers and their content hashes.

**Nothing is reproducible in the abstract.** A run is reproducible against a
stated corpus, at a stated commit, with stated versions. `manifest.describe()`
should return that sentence, filled in, and it should appear at the top of any
difference report.

## The difference report

`make replay RUN=<id>`, or a `replay.py` entry point on Windows, performs audit
replay and prints a difference report. When a replay disagrees, the report must
answer the chapter's question: **which of three things moved, the code, the
model, or the world?** Structure it that way explicitly, with a section per
candidate:

- Code: does `git_commit` differ, was the tree dirty, does the lockfile hash
  differ?
- Model: does any model version in the manifest differ from what is configured
  now?
- World: does any input hash or external response hash differ?

A report that says only "outputs differ" is not useful. A report that says
"four external response hashes changed and nothing else did" is.

## Fixtures

- `fixtures/stored_run/`, a complete recorded run with manifest, trace, inputs
  and outputs, for audit replay to reproduce offline.
- `fixtures/drifted_run/`, the same run with four external response hashes
  changed and everything else identical. This is the chapter's failure account:
  six fewer inclusions, upstream records revised, neither run wrong. The
  difference report must attribute this to the world and not to the code.
- `fixtures/dirty_run/`, a manifest with `git_dirty` true.
- `fixtures/incomplete_run/`, a manifest with status INCOMPLETE and a halt
  reason.

## Gate: `pytest builds/10-run-manifest/tests/`

**`test_audit_replay_reproduces_outputs`**
Replay the stored run from its trace alone, with all network and model access
disabled. Assert every output hash matches. **This must pass with no vendor, no
key and no connection.** Enforce it in the test rather than assuming it:
monkeypatch the model client and any HTTP transport to raise on use. If it
passes only because nothing happened to call out, it does not pass.

**`test_manifest_detects_input_drift`**
Alter one byte of an input; assert verification halts and names the file whose
hash changed. Silence here means the manifest is decorative.

**`test_incomplete_runs_are_marked`**
Assert the incomplete fixture records status INCOMPLETE with a halt reason, and
that a downstream consumer refuses to treat it as finished. This is the Chapter
1 failure, still being guarded against nine builds later.

**`test_dirty_tree_is_recorded`**
Assert `git_dirty` is true in the dirty fixture and that this is disclosed
rather than blocking.

**`test_difference_report_attributes_correctly`**
Run the difference report against the drifted fixture. Assert it attributes the
divergence to the world, names the four changed external hashes, and explicitly
states that the code and the model did not change. Assert it does not report
this as a failure, because neither run was wrong.

**`test_describe_states_its_conditions`**
Assert `manifest.describe()` names the corpus snapshot, the commit and the
model versions.

## Report back

Against the five points in `CLAUDE.md`, plus: confirmation that audit replay
runs with the model client patched to raise, and what your difference report
prints for the drifted fixture. Paste that report in full; it is the clearest
demonstration in the repository of what the book means by provenance.
