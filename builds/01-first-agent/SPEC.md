# SPEC: Build 01, first-agent

**Chapter 3, "Building the Loop by Hand, then Reaching for a Framework".**

## Purpose

A working agent loop in about sixty lines of Python, using the vendor SDK and
nothing else. It exists so a reader can see every one of the five orchestration
decisions as an actual line of code before any framework appears. Clarity beats
cleverness everywhere in this build.

## What the chapter prints

The chapter develops this in five stages, each of which runs on its own. The
repository must contain all five as separate files, because a reader following
the chapter types them in order.

- `stage1.py` A single model call, eleven lines, not yet an agent. Reads the
  model name from the environment.
- `stage2.py` Adds one tool: a `search_pubmed` function plus its declaration.
  The declaration follows the tool description pattern, including the negative
  case ("Do NOT use this to retrieve the text of a known PMID").
- `stage3.py` The loop itself, about twenty-eight lines. This is the core.
- `stage4.py` Adds the `Trace` class, writing JSONL.
- `stage5.py` Adds the remaining three limits: budget, error policy, write gate.

`agent.py` is the assembled version the tests import. It must be the five stages
combined, with no behaviour that did not appear in one of them.

## Public interface

```python
run_agent(task: str, max_steps: int = 20) -> dict
```

Returns a dict with at least: `status`, `steps`, `answer`, `run_id`.

`status` is one of `"COMPLETE"`, `"INCOMPLETE"`, `"FAILED"`.

**On `INCOMPLETE`, `answer` must be `None`.** No partial summary, ever.

```python
dispatch(name: str, args: dict, trace: Trace) -> dict
```

Returns the tool result, or a structured error with `status: "error"` and a
`code`. Never raises to the caller for an expected failure.

```python
class Trace:
    def __init__(self, run_dir: str = "runs") -> None: ...
    def write(self, event: str, **fields) -> None: ...
```

One JSON object per line. Every record carries `run_id`, `ts`, `event`.

## Behaviour required

- Model name from `os.environ.get("AGENT_MODEL", ...)`, one place only.
- Step cap enforced by the loop condition, default 20.
- Budget checked **before** each model call, not after. On exceeding it, halt
  with `status: "INCOMPLETE"` and `reason: "budget"`.
- Error policy: retry only on genuinely transient errors, at most once, with
  backoff. A 429 retries; a 400 never does. Retries count against the step
  budget so a nested loop cannot hide from the ceiling.
- Circuit breaker: after three consecutive failures from the same tool, disable
  that tool for the rest of the run and tell the model it is unavailable.
- Write gate: any tool named in `WRITE_TOOLS` returns
  `{"status": "blocked", "code": "awaiting_human_approval"}` unless approved.
- Termination: the agent signals completion by the SDK's stop reason, and the
  loop distinguishes that from exhausting the cap.

The trace records, at minimum: the model call with its version, each tool
request with its arguments, each tool result with its status, and the
terminating condition with the step count and the cap.

## The stubbed model client

Ship `stub_client.py`. It must be configurable to produce, at least:

- a completion with no tool call (the happy path),
- an unending sequence of tool calls (to drive the step cap),
- a tool call with malformed arguments,
- a transient error then a success (to exercise retry),
- repeated failures from one tool (to exercise the circuit breaker).

Tests use this exclusively. **No test may touch the network.**

## Gate: `pytest builds/01-first-agent/tests/`

Implement these three by name. They are printed in the book.

**`test_step_cap_marks_incomplete`**
Run against a stub that never stops calling tools. Assert `status` is
`"INCOMPLETE"`, `answer` is `None`, and the trace contains a halt event
recording both the step count and the cap.

**`test_invalid_arguments_are_rejected`**
Call `dispatch` with `max_results = -1`, and separately with a two-character
query. Assert both return `status: "error"` with `code: "invalid_arguments"`,
and assert the underlying function was never entered. Validation inside the
function body does not count.

**`test_trace_replays_the_run`**
Run the agent, then reconstruct the sequence of tool calls from the JSONL file
alone. Assert the reconstruction matches what actually happened, including the
model version and the terminating condition.

## Fixtures

`fixtures/` holds the stub scripts driving each scenario above, as data rather
than as code branches where practical.

## Out of scope

No Pydantic schema validation beyond what `dispatch` needs; typed tool
definitions are Build 02. No real PubMed call: `_pubmed_esearch` is a stub
here and is implemented properly in Build 03. No framework, no LangGraph.

## Report back

Against the five points in `CLAUDE.md`, plus: the final line count of
`agent.py`, and whether the twenty-eight line loop from the chapter is still
recognisable inside it.
