# Build 02: Tool Belt

Introduced in Chapter 3 of *The Agentic Lab*, "Building the Loop by Hand, then
Reaching for a Framework", second half.

## What this build does

Build 01 checked tool arguments by hand, so you could see what the checking
consists of. This build replaces those checks with Pydantic models validated at
the dispatch boundary, and adds a second tool so there is something to
misroute.

The gain is not brevity. It is that a malformed call never reaches the function
body, the rejection is written to the trace in a form you can count, and the
model gets back a structured error naming the field that was wrong, which it
can often correct on its next turn.

The declaration shown to the model is generated from the same Pydantic model
that enforces the call, using `model_json_schema()`. Writing it out a second
time by hand is how a declaration and its validator drift apart, and then the
model is told one thing while the code requires another.

## Layout

| File | What it holds |
| --- | --- |
| `dispatch.py` | The schemas, the dispatch boundary, both tools, and the declaration helper. |
| `agent.py` | The loop, unchanged from Build 01: step cap, budget, one retry, circuit breaker. |
| `tracing.py` | `Trace`, the append-only JSONL writer, copied from Build 01. |
| `stub_client.py` | The offline stand-in for the Anthropic client, copied from Build 01. |
| `config.py` | The one place in this build that names a model. |

Nothing here imports from `builds/01-first-agent/`. The two builds are teaching
artefacts read in sequence, not a package, so what this build needs it carries.

## Run it

```
pytest builds/02-tool-belt/tests/
```

The tests need no API key and make no network call: every model response comes
from a fixture replayed by the stub client.

To run the agent for real, set a key and let the model choose the tools:

```
AGENT_MODEL=claude-sonnet-5 python agent.py
```

Run it from inside `builds/02-tool-belt/`, because the modules sit beside each
other rather than in a package.

## A note on running the whole repository at once

Run each build's tests separately, as above. Build 01 and Build 02 both expose
top-level modules called `agent`, `config` and `stub_client`, so a single
pytest process that collects both directories will import one build and hand
those modules to the other. Each gate passes on its own; the two together do
not. See `HANDOFF.md`.
