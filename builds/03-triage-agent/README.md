# Build 03: Triage Agent

Introduced in Chapter 4 of *The Agentic Lab*, "Literature Triage Agents:
Screening That Survives Peer Review".

## What this build does

It screens records against written criteria and records a verdict with a
reason for each one. It is the first build that does real research work, and
the first whose output someone might put in a methods section.

The chapter's argument is that the hardest part of automated screening is not
the agent. It is writing down the criteria you believed you already had. The
build takes that seriously: the criteria are versioned data in
`criteria/repurposing_v3.yaml`, they are validated before anything runs, and a
criteria file that does not validate stops the run rather than falling back to
a default. A screening run that silently used built-in criteria would produce
verdicts nobody could reconstruct.

Four properties are worth stating plainly, because each one is a decision the
chapter argues for rather than an implementation detail.

**Your list drives the loop.** `screen_corpus` walks the identifiers you hand
it. The agent is judging a record it already has, not going looking for one,
which is why `max_steps=4` is generous and why screening offers the model no
tools at all.

**Every record leaves a verdict or a logged gap.** Never nothing. A model call
that fails, or a reply that is not a verdict, produces a `record_failed` event
naming the PMID. The assertion at the foot of `screen_corpus` is not
decoration: it is what makes the accounting true.

**Totals are computed in Python.** The agent is never asked how many records
it screened.

**Ambiguity is flagged, never guessed.** A criterion that cannot be evaluated
from the text is not a criterion that failed. The prompt says so, and it tells
the model the asymmetry that makes flagging the cheaper error: a flagged
record costs a human thirty seconds, a wrong verdict costs a paper.

## Run it

```
pytest builds/03-triage-agent/tests/
```

No API key, no network. Every record comes from the committed fixture corpus
through the cache, and every model reply comes from a stub. One test asserts
that property directly by making `httpx.get` raise.

To screen for real, set a key and point the cache somewhere writable:

```
AGENT_MODEL=claude-sonnet-5 TRIAGE_CACHE_DIR=cache python -c "
from criteria import load_criteria
from screen import screen_corpus
from tracing import Trace
criteria = load_criteria('criteria/repurposing_v3.yaml')
verdicts, failed = screen_corpus(['31562799'], criteria, Trace())
print(verdicts, failed)
"
```

Run it from inside `builds/03-triage-agent/`, because the modules sit beside
each other rather than in a package. Set `NCBI_CONTACT_EMAIL`, and
`NCBI_API_KEY` if you have one: NCBI asks that tools identify themselves and
that unkeyed clients stay within three requests per second, and both are
conditions of use rather than advice.

## Layout

| File | What it holds |
| --- | --- |
| `criteria/repurposing_v3.yaml` | The criteria, as printed in the chapter. |
| `criteria.py` | Loads and validates them, or raises. No default, ever. |
| `models.py` | `Verdict`, as printed. |
| `screen.py` | `screen_corpus`, the driver, as printed. |
| `prompts.py` | The task handed to the model for one record. |
| `agent.py` | The loop from Build 02, returning parsed JSON rather than text. |
| `dispatch.py` | The typed boundary from Build 02, now over real E-utilities. |
| `eutils.py` | `_pubmed_esearch` and `fetch_abstract`, for real, behind the cache. |
| `cache.py` | Content-addressed cache, SHA-256 over every payload. |
| `tracing.py` | `Trace`, the append-only JSONL writer. |
| `stub_client.py` | Two offline stand-ins for the client. See below. |

Nothing here imports from `builds/01-first-agent/` or `builds/02-tool-belt/`.
Each build stands alone.

## The cache, and why it hashes

`fetch_abstract` writes each retrieved record to `<cache>/<pmid>.json` with the
payload and a SHA-256 taken over it. A second run reads from the cache and
makes no network call.

The hash buys the part that matters later. A cache entry edited or truncated
since it was written is detected rather than screened, because a verdict
produced from a corrupted record is worse than a verdict not produced. This is
the first appearance of the content hashing that Chapter 9 builds into the run
manifest.

Failures are never cached. A record unavailable this morning may be available
this afternoon, and a cached failure would be indistinguishable from a real
absence for ever.

## The two stubs

`ScriptedClient` replays a fixture turn by turn, and answers questions about
what the loop does when a call fails or a reply is malformed.

`ScreeningClient` actually screens: it reads the record named in the prompt and
applies the criteria in a few dozen lines of Python. It exists so that
screening the corpus is a real comparison against `gold.json` rather than a
rehearsal of answers written into a fixture. A scripted stub asked whether the
corpus is labelled correctly can only tell you what you already typed.

It is a stand-in for reading comprehension, not a screening tool, and it is
fallible in instructive ways. Its first version read the sentence "no viability
percentage, IC50 or EC50 was determined" as evidence that an IC50 *was*
determined, because it found the acronym and then found a digit nearby: the
digits belonged to the second acronym. That is keyword matching without reading
polarity, which is the failure the fixture corpus was built to catch, and the
corpus caught it.

## The fixture corpus

Sixty-one fabricated records at 14.8 per cent prevalence. **No PMID is real
and no abstract text is taken from a real paper.** See
`fixtures/README.md`, which says so at greater length and explains the seven
records designed to be got wrong by a plausible screen.

`fixtures/gold.json` holds the label for every record and the reasoning for
the seven designed ones. `test_every_verdict_matches_gold` screens all
sixty-one and compares, so a label that drifts from the record it describes
fails the build rather than being discovered by a reader.

## What is not here

Two independent screens, agreement statistics and adjudication are Build 04.
This build produces one set of verdicts.
