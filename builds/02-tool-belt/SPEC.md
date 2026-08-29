# SPEC: Build 02, tool-belt

**Chapter 3, "Building the Loop by Hand, then Reaching for a Framework",
second half.**

## Purpose

Replace Build 01's hand-written argument checks with typed tool definitions
validated by Pydantic at the dispatch boundary. The reader has just seen the
manual version, so this build exists to show what a schema buys them: a
malformed call never reaches the function body, the rejection is logged in a
form you can count, and the model receives a structured error naming the
specific problem so it can often correct itself on the next turn.

This is the build where CLAUDE.md rule 5 applies in full.

## Relationship to Build 01

Build 02 is a separate folder and must run on its own. Do not import from
`builds/01-first-agent/`. Copy what you need. The two builds are teaching
artefacts read in sequence, not a package.

The agent loop itself is unchanged from Build 01. Only `dispatch` and the tool
declarations change.

## What the chapter prints

One listing, extracted to `listings/ch03/06_build02_pydantic_dispatch.txt`.
It must appear verbatim in `builds/02-tool-belt/dispatch.py`. The manifest
entry is currently `mode: skip`; change it to `mode: exact` when this build
exists, and make the test pass.

## Public interface

```python
class SearchPubMed(BaseModel):
    query: str = Field(min_length=3)
    max_results: int = Field(default=20, ge=1, le=200)

SCHEMAS: dict[str, type[BaseModel]]

dispatch(name: str, args: dict, trace: Trace) -> dict
```

`dispatch` behaviour, in order:

1. Look up the schema. Unknown tool returns
   `{"status": "error", "code": "unknown_tool", "tool": name}`.
2. Validate. On `ValidationError`, write a `tool_rejected` event to the trace
   carrying the tool name and the error count, then return
   `{"status": "error", "code": "invalid_arguments", "detail": <first msg>}`.
3. Only on success, call the registered function with the validated values.

The underlying function must never be entered with invalid arguments. That is
the property the gate tests.

## Additional requirement not in the printed listing

Generate the JSON schema for each tool declaration from the Pydantic model
using `model_json_schema()`, rather than hand-writing it a second time. The
chapter says the repository does this. It matters because a hand-written
declaration and a Pydantic model will drift, and then the model is told one
thing while the code enforces another.

Provide a helper:

```python
def tool_declaration(name: str, description: str, schema: type[BaseModel]) -> dict
```

returning the shape the Anthropic SDK expects, with `input_schema` taken from
the model.

## At least two tools

Build 01 had one tool, so nothing could be misrouted. Build 02 must declare at
least two, so the reader sees a real tool belt and so the descriptions have to
disambiguate. Add `fetch_abstract`:

```python
class FetchAbstract(BaseModel):
    pmid: str = Field(pattern=r"^\d{1,8}$")
```

Its description must follow the Table 2.3 pattern from Chapter 2, including the
negative case pointing at `search_pubmed` by name.

## Gate: `pytest builds/02-tool-belt/tests/`

**`test_schema_rejects_before_function_body`**
Register a tool whose function raises on entry. Call `dispatch` with invalid
arguments. Assert the return is `status: error`, `code: invalid_arguments`, and
that the function never raised, proving it was never entered.

**`test_rejection_is_logged_to_trace`**
After a rejected call, assert the trace file contains a `tool_rejected` event
naming the tool. This is the signal that tells you which tool descriptions are
failing, so it must be present and countable.

**`test_declaration_matches_schema`**
Assert the `input_schema` in each tool declaration is exactly
`Model.model_json_schema()`. This is the drift check: a hand-edited declaration
fails here.

**`test_two_tools_are_distinguishable`**
Assert both tools are declared, that each description contains an explicit
negative case, and that neither description is a substring of the other.

No test may touch the network. Reuse the Build 01 stub client pattern; copy it
into this build rather than importing it.

## Out of scope

No framework. No real PubMed call. The write gate, budget and circuit breaker
stay as they were in Build 01; this build is about the boundary, not the loop.

## Report back

Against the five points in `CLAUDE.md`, plus confirmation that
`tests/test_listings.py` passes with the manifest entry changed from `skip` to
`exact`.
