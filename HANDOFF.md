# Session handoff

Last updated 2026-08-29, after the round of book fixes.

**Everything asked for is done and all five gates are green.** Nothing was
pushed. Three items below want a ruling from you; none of them blocks anything.

## Status

| Gate | Result |
| --- | --- |
| `pytest` from the repository root | 29 pass |
| `pytest tests/test_listings.py` | 7 pass, listing 05 included for the first time |
| `pytest builds/01-first-agent/tests/` | 11 pass, no API key present |
| `pytest builds/02-tool-belt/tests/` | 11 pass, no API key present |
| `ruff check builds/` | clean |

Commits this round: `765bf1d` the gate, the listings and the root
configuration; `8a22051` both builds.

## What the book fixes bought

Listing 05 now prints at its real indentation with the write gate inside
`dispatch`, and `stage5.py` matches it. That was the blocked item, and it is
closed. Listing 04 splitting its imports removed the need for the three
`# ruff: noqa: I001` suppressions, which are gone: the corrected listing is
ruff-clean as printed, and where ruff wanted a second blank line before
`class Trace`, a blank line is invisible to `normalise()` anyway.

One thing worth recording, because it caught me out. The fragment check is
order-sensitive as well as indentation-sensitive: `_missing_in_order` advances
a cursor, so the printed budget block appearing before `dispatch` means
`dispatch` has to sit **below** `run_agent` in `stage5.py`. It reads fine, and
a comment there says why, but a future listing reordered on the page will move
code in the repository.

## Task 1: agent.py now has stage5.py's gate

`dispatch(name, args)` with `REGISTRY`, the write gate inside it,
`TransientError` and the printed one-retry loop. `approved` is a function
reading an out-of-band `APPROVALS` set rather than a boolean keyword, so the
model cannot assert its own approval. Since `dispatch` has no trace to write
to, the loop records the refusal from the structured result: `tool_blocked`
for a blocked write, `tool_rejected` for an error.

Two consequences you should know about:

- **Two Build 01 tests changed shape.** `test_invalid_arguments_are_rejected`
  and `test_unknown_tool_returns_a_structured_error` called `dispatch` with a
  trace, which no longer exists. Both keep every assertion the spec names.
  The trace assertion I had added to the first one moved into a new test,
  `test_rejections_reach_the_trace`, which drives the loop with the
  `malformed_arguments` fixture, so rule 5 is still covered end to end.
- **The budget seed changed.** `estimated_next` starts at 0 rather than a
  constant, because nothing has been measured before the first call. A budget
  smaller than one turn therefore no longer prevents the first call; it stops
  the second. That is what `test_budget_halts_before_the_call` asserts.

Build 01 spec report-back: `agent.py` is 345 lines, `run_agent` is 113 of
them and `dispatch` 30. The chapter's loop is still recognisable inside
`run_agent`: the same seven statements in the same order, with the trace
calls, the budget check and the circuit breaker interleaved.

## Task 2: pytest runs from the root

`pyproject.toml` sets `--import-mode=importlib` and `testpaths`.

**That alone was not sufficient, and the way it failed is worth knowing.**
With only the import mode set, `pytest` from the root reported 29 tests
collected and 27 passed. It was wrong. `--import-mode=importlib` settles how
pytest imports *test* modules; it does nothing about the builds' own top-level
modules. Both builds carry `agent.py`, `config.py` and `stub_client.py`, and
Python caches by name, so Build 02's `from agent import run_agent` was handed
Build 01's `agent`. Build 02's loop test then exercised Build 01's loop and
passed anyway, because the two loops are similar enough.

A green run measuring the wrong build is worse than a red one. Two things now
prevent it:

- each build's `tests/conftest.py` drops any cached module that came from a
  different build before importing its own;
- both builds carry `test_this_build_imported_its_own_modules`, which asserts
  the module under test was loaded from that build's own folder. This is the
  test that caught the false pass, and it fails loudly if the arrangement ever
  stops working.

## Task 3: suppressions and the source field

The three `# ruff: noqa: I001` lines are gone, from `stage4.py`, `stage5.py`
and `builds/02-tool-belt/tracing.py`. Build 02's `search_pubmed` returns the
printed `{status, count, pmids}`; the assertion on `source` came out of
`test_valid_call_reaches_the_function` with it.

## Task 4: the gate is committed

`listings/`, `tests/` and `pyproject.toml` are under version control, so a
clean checkout can run the conformance gate. `CLAUDE.md` went in with them:
it had been replaced outside the session, and the code in the same commit
follows the new rule 1 and rule 7 wording, so leaving it uncommitted would
have left the repository following rules it did not record.

## Three things wanting a ruling

1. **`builds/01-first-agent/SPEC.md` is now stale.** Line 43 still declares
   the public interface as `dispatch(name: str, args: dict, trace: Trace)`.
   The code has `dispatch(name, args)`, because you ruled the printed form
   wins. The spec and the book now disagree in writing. I did not edit the
   spec: it is yours. One line.

2. **`agent.py` and `stage5.py` still differ below the gate.** The gate is
   identical now, but not everything else is:
   - `agent.py`'s `search_pubmed` returns `{status, count, results, source}`
     with whole records; `stage5.py` returns the printed
     `{status, count, pmids}`.
   - the two tool descriptions differ in wording from the printed ones.
   - `agent.py` uses `MAX_TOKENS = 1024`; the stage files use 2048 as printed.

   This matters because `agent.py`'s own docstring says it is "stage1 through
   stage5 in one file, with nothing in it that did not appear in one of them",
   and that sentence is currently false. Either the file should move the rest
   of the way or the docstring should stop claiming it. I did not choose,
   because your instruction was specific to the gate and the return shape
   change would touch fixtures and assertions.

3. **`fetch_abstract` still returns a `source` field.** Rule 7 says a listing
   wins where it conflicts, and forbids adding provenance a listing does not
   print. No listing prints `fetch_abstract` at all, so the rule is silent
   rather than decisive. It reads inconsistently beside `search_pubmed`, which
   no longer carries one. Say which way and it is a one-line change.

## Smaller notes

- `Trace` exists twice in slightly different form: `builds/02-tool-belt/
  tracing.py` is the printed version, while `builds/01-first-agent/agent.py`
  still uses `uuid4()` and `record.update(fields)`. Both behave identically
  and only the stage files are checked against the listing.
- Line endings: git reports LF being replaced by CRLF on checkout for every
  file committed. That is the default Windows behaviour and harmless here,
  since `normalise()` strips carriage returns before comparing, but a
  `.gitattributes` would silence the warnings if they bother you.

## Not started

Build 03. It has no spec, and inventing one is not mine to do.
