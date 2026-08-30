# Fixture corpus for Build 10

## Everything here is fabricated

**No record, endpoint, digest, commit hash or lock file in this folder
corresponds to anything real.** The thirty-six records are invented, the
enrichment endpoint `https://enrichment.example/v1/records` resolves nowhere,
the commit `4f1c9ae3...` is not in any repository, and the model
`stub-screener@2026-05-01` does not exist.

The digests, however, are real digests of these fabricated bytes. That is the
point: every hash in every manifest here was computed from a file this folder
contains, so the replay machinery is checking arithmetic rather than being told
the answer.

## The output is generated, and the generator is committed

`make_fixtures.py` writes all four runs. Run it from the build directory:

```
python fixtures/make_fixtures.py
```

It is committed because the drifted run has to be a *fair* version of the
chapter's failure account, and a reader should be able to check that it is
rather than take it on trust. Four external responses revised, the code and the
model untouched, and six fewer inclusions arriving **as a consequence** rather
than as a number typed into a summary file. The six revised records are chosen
by walking the included set in order, and the generator raises if that does not
land on exactly six records across exactly four batches, so the fixture cannot
quietly stop being what it claims while still looking plausible.

What it prints is what the gate asserts:

```
  stored:   16 included of 36
  drifted:  10 included, 6 fewer
  revised upstream records: REC-004, REC-005, REC-007, REC-008, REC-013, REC-019
  external responses changed: 4 of 6
```

It is deterministic. The clock is injected, the JSON is canonical with sorted
keys, and running it twice produces byte-identical output, which it has to:
every digest in every manifest is a hash of bytes this file wrote, so a wall
clock anywhere in it would make the committed fixtures disagree with their own
generator on the next run.

## The four runs

Each directory holds `manifest.json`, a `.jsonl` trace, `inputs/` and
`outputs/`.

### `stored_run/`

A complete recorded run: 36 records, 6 enrichment calls of 6 records each, 36
model completions, 16 inclusions. `audit_replay` rebuilds both outputs from
this trace alone with the network cut.

The trace is the interesting file. It holds `external_call` events carrying the
**response bodies**, and `model_completion` events carrying the **raw
completion text**. Neither is a conclusion this build drew. That is why an
offline replay four years from now can still recompute a response digest and
still rebuild the verdicts, and it is the single design decision the whole
build rests on.

### `drifted_run/`

The same run, later. Four of the six enrichment responses were revised
upstream, six records that qualified no longer do, and the outputs differ. The
commit, the lock file, the model version, the temperature, the seed and all
three input files are identical.

This is the chapter's failure account, and the difference report has to
attribute it to the world and say plainly that the code and the model did not
change. Neither run is wrong. They are correct accounts of two different states
of the world.

### `dirty_run/`

`git_dirty: true`, and otherwise a complete run that replays successfully. The
fixture exists to demonstrate that a dirty tree is **disclosed rather than
blocked**: `audit_replay` reproduces it, and the difference report reports the
uncommitted changes as a finding under CODE with the note that the commit hash
does not identify the code that ran.

### `incomplete_run/`

`status: INCOMPLETE` with a halt reason, produced by actually stopping the run
after 20 of 36 records rather than by writing INCOMPLETE onto a finished run. A
fixture that agreed with the test and disagreed with reality would be worse
than no fixture.

It has partial outputs, and that is exactly why the guard matters: there is
something there to summarise, and summarising it is Chapter 1's failure. The
downstream consumer, `require_complete`, raises `IncompleteRun` whose
structured form carries `"answer": None`.

## What the fixtures deliberately do not include

No real lock file hash from this repository, no real git commit, and no real
Python build. Those would make the fixtures depend on the machine they were
generated on, and the whole argument of this build is that a run should be
replayable somewhere else.
