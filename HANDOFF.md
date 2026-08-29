# Session handoff

Unattended session, 2026-08-29. Two tasks were set: apply the listing rulings
to Build 01, then implement Build 02.

Both are committed. One item is blocked and needs a ruling from you. Nothing
in `listings/` was edited except the single Build 02 mode line you authorised.

## Status at a glance

| Gate | Result |
| --- | --- |
| `pytest tests/test_listings.py` | 6 pass, 1 fails: `05_stage5_limits`, and it cannot be made to pass. See below. |
| `pytest builds/01-first-agent/tests/` | 9 pass, no API key present |
| `ruff check builds/01-first-agent/` | clean |
| `pytest builds/02-tool-belt/tests/` | 10 pass, no API key present |
| `ruff check builds/02-tool-belt/` | clean |

Commits: `7abb64e` Build 01, `dfc60a6` Build 02. Nothing was pushed.

## The blocked item: listing 05 cannot pass, and the repository is not why

`05_stage5_limits.txt` is checked in `fragment` mode. Five of its lines can
never appear in any valid Python file, so no change to `stage5.py` will make
the check pass.

The book prints the three snippets dedented, lifted out of the function they
belong to. `_missing_in_order` in `tests/test_listings.py` compares whole
lines with their leading whitespace intact, so a printed line at column 0 only
matches a repository line at column 0. Two of the three snippets put a
`return` at four spaces under an `if` at column 0:

```
if tokens_used + estimated_next > TOKEN_BUDGET:
    trace.write("halt", reason="budget")
    return {"status": "INCOMPLETE", "reason": "budget", "steps": steps}
```

Placed at that indentation the file does not compile:

```
SyntaxError: 'return' outside function
```

That is the whole of the failure. The five unmatched lines are the three
budget lines and the two write gate lines. The printed `dispatch`, all twelve
lines of it, now matches `stage5.py` verbatim, which is why it no longer
appears in the missing list.

I did not touch the listing, the manifest mode, or `normalise()`. Changing
`normalise()` to ignore leading whitespace would make the check pass, and I
think that is the wrong fix: it would let differently indented code satisfy a
listing, which is most of what the check exists to catch.

Three ways out, for you to choose:

1. Print those two snippets at the indentation they really have, inside the
   loop and inside `dispatch`. The check then passes untouched. This is the
   only option that keeps the check as strict as it is now.
2. Split listing 05 into three files and mark the two dedented ones
   `mode: skip` with a stated reason.
3. Add a `dedent: true` option to the manifest and have the test compare after
   removing the common leading whitespace from both sides. Weaker than option
   one, stronger than stripping all indentation.

The behaviour the snippets describe is implemented in `stage5.py` either way:
the budget is checked before the call using `tokens_used + estimated_next >
TOKEN_BUDGET`, `REGISTRY` and `TransientError` exist, the tool level retry is
the printed `for attempt in (1, 2)`, and the write gate is a function.

## Task 1: Build 01, against the five points in CLAUDE.md

1. **Tests pass with no API key.** 9 passed. Run with `ANTHROPIC_API_KEY`
   unset to confirm.
2. **Ruff clean.** Yes.
3. **README states what, how and which chapter.** Unchanged and still
   accurate; it already used `claude-sonnet-5` in its example.
4. **Every listing in the chapter exists and behaves as printed.** True for
   listings 01 to 04. Listing 05 is the blocked item above.
5. **Report.** This document.

What changed: `stage1.py` took the explicit `api_key` form, the
`claude-sonnet-5` default and the ivermectin prompt. `stage2.py` took `TOOLS`,
`max_results=20` and the `{status, count, pmids}` return shape. `stage3.py`
gained `MAX_STEPS`, `tools=TOOLS`, `max_tokens=2048` and the assistant message
appended before the `stop_reason` test. `stage4.py` carries the printed
`Trace`. `stage5.py` took the budget, error policy and write gate described
above, and kept the circuit breaker as an addition. `agent.py` and `config.py`
follow the same timezone and model rulings.

Stages 1 to 4 were assembled by splicing the listing file itself into the
repository file rather than retyping it, so the continuation line indentation
matches byte for byte.

**Your expectation that two of the five would pass without repository changes
did not hold.** Listings 03 and 04 needed the repository to move as well: the
corrections you made on the book side fixed `content[0].text` and `time.time()`,
but 03 still wanted `MAX_STEPS`, `tools=TOOLS` and `max_tokens=2048`, and 04
still wanted `import json, uuid`, `uuid.uuid4()` and the `record = {...**fields}`
form. Both pass now.

## Task 2: Build 02, against the five points in CLAUDE.md

1. **Tests pass with no API key.** 10 passed. The four the spec names are
   present under exactly those names; six more were added.
2. **Ruff clean.** Yes.
3. **README states what, how and which chapter.** Rewritten.
4. **Every listing in the chapter exists and behaves as printed.** Listing 06
   appears verbatim in `dispatch.py` and the manifest entry is now
   `mode: exact`. It passes.
5. **Report.** This document.

The spec is satisfied as written: schemas validate at the boundary, the
underlying function is never entered with invalid arguments, `ValidationError`
becomes a `tool_rejected` trace event carrying an error count, declarations are
generated with `model_json_schema()`, and `fetch_abstract` is declared with a
description naming `search_pubmed` in its negative case.

## Decisions the specs did not cover

- **`estimated_next` has no definition in the book.** I seeded it from a
  module constant, `ESTIMATED_CALL_TOKENS = 1_500`, and then replaced it after
  each turn with that turn's measured usage, on the argument that the last
  turn is the best available estimate of the next one. If you meant something
  else, this is the line to change.
- **`approved(name, args)` reads a module level `APPROVALS` set, not the
  arguments.** A model asked whether its own write was approved will say yes,
  so approval has to arrive out of band. `args` is deliberately unused.
- **Rejection logging in `stage5.py` moved into the loop.** The printed
  `dispatch` takes two arguments and has no trace to write to, but CLAUDE.md
  rule 5 requires rejections to reach the trace. The loop writes the
  `tool_rejected` event from the returned structured error instead.
- **Hand written bounds are `1 <= max_results <= 200`** in stages 3 to 5, to
  match the `le=200` that Build 02's Pydantic model declares, so the claim that
  the behaviour does not change when the schema arrives is actually true.
- **Build 02 declares no write tools.** Both its tools read. `WRITE_TOOLS` is
  an empty set and the gate is retained for the build that adds one.

## Things I think are wrong

1. **Listing 05.** The blocked item above. Needs your ruling.
2. **Listing 02 makes the repository state something false.** The printed
   docstring is `"""Real implementation lives in the repo. Stub shown here."""`
   and `fragment` mode requires that exact line to appear in `stage2.py`. It is
   now in stages 2, 3, 4 and 5, where it is untrue: those files are the repo.
   Suggest rewording the printed docstring to something that is true in both
   places, for instance `"""Stubbed until Build 03 replaces the body."""`.
3. **Listing 04 prints `import json, uuid`, which ruff rejects.** I001 fires on
   the combined import. I suppressed it with a file level `# ruff: noqa: I001`
   in `stage4.py`, `stage5.py` and `builds/02-tool-belt/tracing.py`, because a
   comment line is dropped by `normalise()` and so cannot break the match. It
   would be cleaner for the book to print the two imports on separate lines.
4. **`stage5.py` and `agent.py` now disagree inside Build 01.** `stage5.py` has
   the printed `dispatch(name, args)` with `REGISTRY`, `TransientError` and
   `approved()`. `agent.py` still has `dispatch(name, args, trace)` with a
   boolean `approved` keyword and per tool check functions. Task 1 named only
   `stage5`, and `agent.py` carries the nine tests, so I left it. A reader who
   moves from the last stage to the finished build sees two different gates.
   Worth a ruling, and it is a small change once you have made one.
5. **`pytest` from the repository root fails, though every individual gate
   passes.** Both builds expose top level modules named `agent`, `config` and
   `stub_client`, and both `conftest.py` files prepend their own build to
   `sys.path`. One pytest process imports whichever build it reaches first and
   hands those modules to the other, so Build 01's tests end up calling Build
   02's `agent`. The fix is a root `pyproject.toml` setting
   `--import-mode=importlib`, or unique module names per build. I did not make
   it: root files were out of bounds for this session. Until then the gates
   have to be run one build at a time, which is how CLAUDE.md and both specs
   define them. Noted in Build 02's README.
6. **Rule 7 versus listing 02.** The printed return shape is
   `{"status", "count", "pmids"}` with no `source`. CLAUDE.md rule 7 makes
   provenance required. The stage files follow the book and omit it; Build 02's
   `search_pubmed` includes `source`. One of the two should move.
7. **Rule 1 versus self-contained stage files.** Rule 1 says the model name
   appears in at most one place per build. Each stage file must stand alone, so
   Build 01 names it five times, once per stage, plus `config.py`. The rule and
   the self-containment decision cannot both hold as written. Suggest the rule
   say "at most one place per runnable artefact".

## State you should know about

`listings/` and `tests/` are untracked, and I left them that way because you
replace `listings/` from outside this session. That has one consequence worth
seeing: **the manifest change from `mode: skip` to `mode: exact` exists only in
your working tree.** It is in no commit. If you replace `listings/` again from
your external copy, that edit is lost and listing 06 goes back to being
skipped.

A clean checkout of this repository has neither the listings nor
`tests/test_listings.py`, so the conformance gate cannot run there at all. If
that gate is meant to protect readers, it probably wants to be committed.

`builds/02-tool-belt/SPEC.md` was untracked; I committed it with Build 02, to
match Build 01 where `SPEC.md` is tracked.

## Not started

Build 03. It has no spec, and inventing one is not mine to do.
