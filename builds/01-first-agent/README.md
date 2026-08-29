# Build 01: First Agent

Introduced in **Chapter 3, "Building the Loop by Hand, then Reaching for a
Framework"**, of *The Agentic Lab*.

## What this build does

A working agent loop written against the Anthropic SDK and nothing else. It
searches a stubbed PubMed, writes a replayable trace, and stops when it is
told to stop or when it runs out of room. There is no framework here on
purpose: every one of the five orchestration decisions is an ordinary line of
Python you can point at.

| Decision | Where it lives |
|---|---|
| Step cap | the `while steps < max_steps` condition in `run_agent` |
| Trace | the `Trace` class, one JSON object per line |
| Budget | checked at the top of the loop, **before** the model call |
| Error policy | `is_transient`, one retry with backoff, plus the circuit breaker |
| Write gate | `WRITE_TOOLS` in `dispatch` |

Two things the loop will not do. It never invents an answer from partial
work: a run that reaches the step cap returns `INCOMPLETE` with `answer` set
to `None`. And it never asks the model to count anything: `search_pubmed`
computes its own `count` in Python, because a model asked to count will
sometimes be wrong and will never say so.

## The files

The chapter builds this in five stages, each of which runs on its own. Type
them in order; each imports from the one before it, so nothing is typed twice.

| File | What it adds |
|---|---|
| `config.py` | The one place in the build that names a model. |
| `stage1.py` | A single model call. Eleven lines, and not yet an agent. |
| `stage2.py` | One tool: `search_pubmed`, and the declaration that describes it. |
| `stage3.py` | The loop, and the `dispatch` boundary that validates arguments. |
| `stage4.py` | The `Trace` class, writing JSONL. |
| `stage5.py` | Budget, error policy, write gate. |
| `agent.py` | The five stages assembled into one importable module. |
| `stub_client.py` | A stand-in for `anthropic.Anthropic`, driven by `fixtures/`. |

`agent.py` contains nothing that did not appear in one of the stages. Its
`run_agent` is the twenty-eight line loop from stage 3 with the limits from
stages 4 and 5 folded in.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # a real key, for the stages only
cd builds/01-first-agent
python stage1.py                    # one call
python agent.py                     # the whole loop
```

The model name comes from the environment, never from the source:

```bash
AGENT_MODEL=claude-sonnet-5 python agent.py
```

See [MODELS.md](../../MODELS.md) for the current names. The default is in
`config.py` and appears exactly once in this build.

Traces land in `runs/<run_id>.jsonl`, one event per line. To see what a run
actually did, read the file rather than the return value:

```bash
python -c "import json,sys; [print(json.loads(l)['event']) for l in open(sys.argv[1])]" runs/<run_id>.jsonl
```

## Test it

```bash
pytest builds/01-first-agent/tests/
```

The tests never reach the network, and they pass with no API key present.
Every model response comes from a script in `fixtures/`, replayed by
`stub_client.StubClient`, which presents the same surface as the real client:
swapping one for the other requires no change to `agent.py`.

| Fixture | Drives |
|---|---|
| `happy_path` | One search, then an answer. |
| `step_cap` | A model that never stops calling tools. |
| `malformed_arguments` | A tool call with a negative `max_results`. |
| `transient_then_success` | A 429, then a clean answer. |
| `permanent_error` | A 400, which must never be retried. |
| `tool_failure_loop` | The same tool rejected four times, to open the breaker. |
| `write_attempt` | A write with no human approval behind it. |

## Known limits, and what comes next

- `_pubmed_esearch` is a stub over four hard-coded records. Build 03 gives it
  a real esearch call and keeps the signature.
- Arguments are validated by hand in `check_search_pubmed` and
  `check_save_note`, so you can see what the checks are before a schema hides
  them. Build 02 replaces them with Pydantic; the observable behaviour does
  not change.
- Nothing in this build can approve a write. `dispatch` takes an `approved`
  flag and `run_agent` never passes it, so `save_note` always returns
  `awaiting_human_approval`. The approval path is a later chapter.
