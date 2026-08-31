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

`pytest` from the repository root runs everything, this build included.

That takes a little arranging, because Build 01 and Build 02 both carry
modules called `agent`, `config` and `stub_client`: each build has to stand
alone for a reader who opens only that folder. Python caches modules by name,
so without help the build collected first would hand its modules to the
second. Two things prevent it. `pyproject.toml` sets
`--import-mode=importlib`, which settles the test module names, and the
repository root `conftest.py` keeps exactly one build importable at a time,
moving the other builds' modules into a per-build cache and putting them back
when that build runs again. They are parked rather than discarded: a module
that is thrown away gets re-executed on the next import, which quietly
produces a second copy of every class in it.

The `tests/conftest.py` in this folder does something smaller and separate. It
puts this build's directory on the path, so a reader who copies out only this
folder still gets `import config` working.

Both builds also carry `test_this_build_imported_its_own_modules`, which fails
loudly if that ever stops working. Without it the symptom is not an error: the
wrong build is measured and the tests still pass.
