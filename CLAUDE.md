# CLAUDE.md

Standing instructions for this repository. Read this before doing anything.

## What this repository is

Companion code for the book **The Agentic Lab: Build AI Agents for Biotech and
Pharma R&D** by Suryaprakash Tripathy. Twelve builds, one per folder under
`builds/`, each introduced by a chapter of the book.

The book is already written. **The chapters are the specification.** Your job is
to implement what a chapter describes, not to design something better. If you
believe a design in a chapter is wrong, say so and stop; do not silently improve
it. A reader typing code from the printed page must get the same behaviour as
the repository, and a mismatch between page and repo is the single worst defect
this project can ship.

## Scope discipline

- **One build per session.** Do not start build N+1 because build N finished
  early. Stop and report.
- Every build has a `SPEC.md`. If it is missing, stop and ask for it. Do not
  infer the spec from the folder name.
- Do not create folders, builds, or top-level files that are not in the spec.

## Non-negotiable conventions

These come from the book's arguments and every build must follow them.

1. **Model name from configuration, never from source.** Read it from the
   environment with a default, as `os.environ.get("AGENT_MODEL", ...)`. It must
   appear in at most one place **per runnable artefact**. The assembled build
   reads it from `config.py`. Teaching stage files each name it once, because
   each must run on a machine holding only that one file.
2. **A run that exhausts its step cap returns `INCOMPLETE` with `answer: None`.**
   It never summarises partial work. This is the book's central failure mode.
3. **Arithmetic belongs in Python, never in a model prompt.** Counts, totals,
   unit conversions, percentages. If a spec seems to ask a model for a number,
   re-read it.
4. **Every error path returns a structured object** with `status` and a `code`
   field. Never return prose describing a failure into a model's context.
5. **Validate tool arguments with Pydantic at the dispatch boundary**, before
   the function body runs. Log rejections to the trace.
6. **Units live in column names**, e.g. `conc_nM`, never `conc`.
7. **Provenance fields are required where a spec or a listing names one.**
   Fields such as `source`, `criteria_version` and `approved_by` are required
   when specified, and the code refuses to proceed without them. This rule does
   not license adding provenance fields a listing does not print. Where the
   two conflict, the listing wins: a reader typing the printed return shape
   must get the printed return shape.
8. **Write the trace as JSONL** from the first version, one event per line.

## Testing

- **Tests must never make live API calls.** Use a stubbed model client. Every
  build ships one. If a test would need the network, the test is wrong.
- `pytest builds/<name>/tests/` must pass from a clean checkout with no API key
  present.
- Tests are specified in the `SPEC.md` by name and by what they assert. Implement
  those exactly. You may add more; you may not omit or rename any.
- Prefer a fixture over a mock. Broken-input fixtures live in
  `builds/<name>/fixtures/` and are committed.

## Things you must not do

- **Do not `git push`.** Commit locally and stop. The human reviews and pushes.
- **Do not commit `.env`**, or any file containing a key. Check `git status`
  before every commit.
- **Do not use `sudo`.** A permission error means the virtual environment is not
  activated.
- **Do not add dependencies** not already in `requirements.txt` without asking
  first and explaining why.
- **Do not edit anything in `listings/`.** Those files are the printed book.
  If a conformance test fails, the repository is wrong. Report the mismatch
  and stop.
- **Do not upgrade or reformat code in other build folders.** Stay in your build.
- **Do not delete or rewrite `MODELS.md`, `README.md`, or another build's files.**

## Style

- Python 3.11+, type hints on public functions, `ruff`-clean.
- Comments explain **why**, not what. The book explains what.
- Prose in READMEs and docstrings uses British spellings, to match the book.
- **No em dashes or en dashes anywhere**, including comments and documentation.
  Use commas, colons, or separate sentences. This is a house rule for the whole
  project and it is checked.
- Keep printed-in-the-book code short enough to type. If a function in the book
  is twenty lines, the repository version may be longer, but the twenty lines
  must still be recognisable inside it.

## Definition of done for a build

1. `pytest builds/<name>/tests/` passes with no API key present.
2. `python3 -m ruff check builds/<name>/` is clean.
3. `builds/<name>/README.md` states what it does, how to run it, and which
   chapter introduces it.
4. Every code listing that appears in the corresponding book chapter exists in
   the build and behaves as printed.
5. A short report to the human: what you built, what you had to decide that the
   spec did not cover, and anything in the spec you think is wrong.

Report against these five points at the end of every session.
