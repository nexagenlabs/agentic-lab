# Conventions

How this repository is built, and why it is built that way.

This is companion code for **The Agentic Lab: Build AI Agents for Biotech and
Pharma R&D** by Suryaprakash Tripathy. Twelve builds live under `builds/`, one
per folder, each introduced by a chapter of the book.

Most of what follows is a decision that cost something to arrive at. Where a
rule has a story behind it, the story is here too, because the rule on its own
reads as arbitrary and gets undone by the next person who finds it
inconvenient.

## The chapters are the specification

The book is already written, and the code in it is printed. A reader typing
code from the printed page must get the same behaviour as the repository. A
mismatch between page and repo is the single worst defect this project can
ship, because print cannot be patched.

That is the reasoning behind the conformance gate, and behind the shape of
several decisions further down that would otherwise look perverse.

### Listing conformance

`listings/` holds the code exactly as it appears in the book, with
`listings/manifest.yaml` mapping each listing to the file in `builds/` that
must match it. `tests/test_listings.py` compares the two.

The files in `listings/` are the printed book. They are not edited to make a
test pass. When conformance fails, the repository is wrong and the repository
is what changes, because the page is the expensive half to change and by the
time anyone notices it may already be in print.

The same reasoning governs paths. `tests/test_artefacts_exist.py` checks every
path the book names against the tree, and checks that each one holds
something, because a zero byte file passes every existence check ever written
and fails a reader immediately. It exists because an appendix printed a tree
listing three templates and two of them did not exist. A reader following a
printed tree to a missing file gets a worse first impression than a missing
feature, since it says the tree was never checked.

## Conventions every build follows

These come from the arguments the book makes, and the builds are consistent
about them.

1. **Model name from configuration, never from source.** It is read from the
   environment with a default, as `os.environ.get("AGENT_MODEL", ...)`, and it
   appears in at most one place *per runnable artefact*. The assembled build
   reads it from `config.py`. Teaching stage files each name it once, because
   each has to run on a machine holding only that one file.
2. **A run that exhausts its step cap returns `INCOMPLETE` with
   `answer: None`.** It never summarises partial work. This is the book's
   central failure mode, and a partial summary is exactly the output that
   hides it.
3. **Arithmetic belongs in Python, never in a model prompt.** Counts, totals,
   unit conversions, percentages.
4. **Every error path returns a structured object** with `status` and a `code`
   field. Prose describing a failure is never returned into a model's context.
5. **Tool arguments are validated with Pydantic at the dispatch boundary**,
   before the function body runs, and rejections are logged to the trace. A
   rejection nobody can count is a rejection nobody will fix.
6. **Units live in column names**, as `conc_nM` rather than `conc`.
7. **Provenance fields are required where a spec or a listing names one.**
   Fields such as `source`, `criteria_version` and `approved_by` are required
   where specified, and the code refuses to proceed without them. This does
   not license adding provenance fields a listing does not print. Where the
   two conflict the listing wins, because a reader typing the printed return
   shape must get the printed return shape.
8. **The trace is JSONL** from the first version, one event per line.

## Cross-build imports: settled

Builds deliberately share module names. Four carry `config.py`, five carry
`models.py`, four carry `tracing.py`, and they import each other's modules by
bare name because the book prints `from config import MODEL` and a reader has
to be able to open one folder and run `python profile.py` inside it.

Two obvious fixes were considered and both are wrong:

- **Renaming modules per build** breaks the printed listings, which is the one
  defect this project treats as unshippable.
- **Making each build a package** breaks the reader. Inside a package,
  `from transform import apply_mapping` is not a valid absolute import, so
  every intra-build import in every build would have to change, and the file a
  reader typed from the page would stop running on its own.

So the repository root `conftest.py` keeps **exactly one build importable at a
time**: one build folder on `sys.path`, one build's modules in `sys.modules`.

The part that is easy to undo by accident: modules of the other builds are
**parked in a per-build cache, not deleted**. Eviction was the earlier
approach, and it means a function-body `import models` re-executes the module
and produces a second copy of every class in it, so `isinstance` starts
returning False for objects that are obviously the right type. That failure is
quieter than the one being fixed. Park, do not evict.

`tests/test_build_isolation.py` asserts the invariant rather than the
mechanism. `PLC0415` in `pyproject.toml` bans function-body imports, so the
shape that causes the collision cannot be written in the first place; the
guard tests are the one exception and carry an explicit `# noqa: PLC0415` with
a comment saying why. Every build ships
`test_this_build_imported_its_own_modules`, and the isolation test fails until
a new build has one.

Build 11 is a deliberate variation rather than an exception. It reaches the
earlier builds through a subprocess boundary instead of the import mechanism,
because an adapter that swapped build 03 onto `sys.path` in the middle of a
build 11 test would be fighting the mechanism rather than using it, and would
fail in precisely the quiet way the mechanism exists to prevent.

## Tools may use the network. Tests may not.

The rule is that **tests never make live API calls**, and it means tests.
`tools/` is not covered by it.

Tests use a stubbed model client, and every build ships one.
`pytest builds/<name>/tests/` passes from a clean checkout with no API key
present. A network call inside `builds/*/tests/` is a defect.

Three files under `tools/` are deliberately exempt, and a network call inside
one of them may be the point of the file:

- `tools/verify_references.py` queries Crossref, and cannot do its job any
  other way. It exists to establish that every reference in Appendix D
  resolves to a real record whose title matches what the book claims, and a
  stubbed Crossref would verify nothing.
- `tools/verify_printed_urls.py` requests every URL printed in the book
  against the live site, over real HTTPS with certificate verification on, and
  asserts where each one lands. `tests/test_site_urls.py` checks the map, that
  `site/_redirects` names paths which exist in this repository, and it runs
  offline. The tool checks the territory: DNS, TLS, whether the site deployed,
  whether GitHub still serves that URL scheme. Neither substitutes for the
  other.
- `tools/generate_qr_codes.py` generates one QR code per printed URL and reads
  each one back with a different library than the one that wrote it. It
  refuses to run unless the URL verification report is present and marks every
  printed path OK, because a QR code encoding a dead URL is worse than no QR
  code: a reader can judge a printed address before typing it, and cannot
  judge a black square before scanning it.

All three are absent from `testpaths` and stay absent. No build imports them.
A suite that fails when the internet is down is a suite people learn to
ignore, and an ignored suite is worse than no suite, because it still looks
like coverage.

## A test that asserts something cannot happen must first be shown to bite

Trigger the prohibition, watch the test fail, and only then assert the thing
that should be safe.

A patch that does nothing, a rule that matches nothing and a stub that never
misbehaves all pass silently. A green test that was never in danger of going
red is decoration. This has been found three times:

- an `importlib` false pass;
- `NaiveDraftingClient` in Build 09, which follows every injected instruction,
  so that the gate is stopping six real attempts rather than congratulating a
  well behaved stub;
- Build 10's `test_audit_replay_reproduces_outputs`, which patches six entry
  points and runs `verify_replay` through them to watch it die, before
  trusting the offline replay that follows.

Build 11 applies the same rule to itself. For every family of fault it names
one the earlier builds miss, runs it against them with nothing added, and
asserts both that it was missed and that the miss was silent. If a later
change makes one of those pass, the test fails and somebody has to decide
whether a real check arrived or the fault stopped being one.

## A ruling that changes what a field means requires checking what reads it

A relaxed definition propagates silently.

`OK` in `verify_printed_urls.py` meant "returns 200" until `/ch01` was ruled
to be correctly returning 404, after which it meant "behaves as intended".
`generate_qr_codes.py` was reading `OK` as "safe to print", and duly produced
QR codes for the two addresses the book does not print. Nothing owned the
relationship between the two meanings, which is Chapter 12's failure account
in miniature, inside the tooling for the book that contains it.

Grep for a field before widening what it means.

## A figure quoted from a specification is not a measurement

If a number will guide a physical decision, measure it.

"Level H tolerates thirty per cent damage" is the specification talking about
codewords, and it told a typesetter nothing useful. Measuring gave a twenty
per cent contiguous blot surviving, twenty-three per cent failing, ten per
cent scattered speckle already fatal, and any damage to a corner square fatal
at any size, because a scanner has to locate a symbol before error correction
can do anything. The last of those is the one that matters, and no
specification figure contains it.

## Fixtures

Tests prefer a fixture over a mock. Broken-input fixtures live in
`builds/<name>/fixtures/` and are committed.

A build that generates its fixtures programmatically ships the generator. Both
the generator and its output are committed, so nothing has to be run to use
the build. A fixture whose provenance nobody can inspect is the thing Chapter
9 argues against, and it is worse than an unchecked one: where a test computes
its number from fixture data rather than reading it from a file alongside, a
fixture that quietly made the check easy turns the check into decoration.
Build 08's `fixtures/make_fixtures.py` is the pattern.

## New top-level directories

Check that a directory is not already ignored before writing the first file
into it.

`site/` was ignored by `/site` in `.gitignore`, a rule inherited from the
standard Python template where it means "mkdocs build output". This repository
has never used mkdocs. Four files were written, `git status` showed nothing,
`git add` said nothing, and there was no error anywhere: the companion site
behind thirteen printed URLs was invisible to version control. The fix was to
remove the rule rather than to work around it, and restoring it would be wrong
for the same reason it was wrong to begin with, because `site/` is hand
written content rather than build output. If mkdocs is ever added, it gets a
different output directory.

`git check-ignore -v <path>` is the check, and it has a trap. Given a
directory that does not exist yet and a trailing slash, it reports a match
against a blank line in `.gitignore` and exits 0 for any name at all, so
`docs/`, `zzz/` and `notreal/` all come back "ignored" when none of them is.
Query the path without a trailing slash, and confirm with the two things that
actually failed during the `site/` incident: `git status` should show the
directory as untracked, and `git add --dry-run` should print the file it
would add.

## Style

- Python 3.11+, type hints on public functions, `ruff`-clean.
- Comments explain **why**, not what. The book explains what.
- Prose in READMEs and docstrings uses British spellings, to match the book.
- **No em dashes or en dashes anywhere**, including comments and
  documentation. Use commas, colons, or separate sentences. This is a house
  rule for the whole project.
- Printed-in-the-book code stays short enough to type. Where a function in the
  book is twenty lines, the repository version may be longer, but the twenty
  lines are still recognisable inside it.

## What a finished build looks like

1. `pytest builds/<name>/tests/` passes with no API key present.
2. `python -m ruff check builds/<name>/` is clean.
3. `builds/<name>/README.md` states what the build does, how to run it, and
   which chapter introduces it.
4. Every code listing appearing in the corresponding book chapter exists in
   the build and behaves as printed.
