# Build 05: Wrangler

Introduced in Chapter 5 of *The Agentic Lab*, "Data-Wrangling Agents for
Omics, Imaging and Instrument Exports".

## What this build does

It reads an unfamiliar instrument export, proposes a column mapping for a
human to approve, and then hands off to deterministic code that does the
transformation under a schema with declared units.

**The agent never touches a number.** It supplies judgement about what a
column means, which is the thing it is good at and the thing no regular
expression does reliably across instruments. Code supplies every
transformation, conversion and total. The prompt says so in as many words:
*do not convert anything, do not total anything, do not comment on whether the
values look reasonable.*

## The four things that carry the build

**Bounded input.** The agent sees fifteen lines and a shape summary, never the
file. That caps cost, caps context growth, and stops the model forming
opinions about values.

**The mapping is data, and it is approved.** `apply_mapping` raises if
`approved_at` is unset. Three lines, and they are what makes the human gate
structural rather than procedural. `propose_mapping` blanks the approval
fields whatever the model said, because a model cannot sign off its own
proposal. Approved mappings live in `mappings/*.yaml` and are replayed
thereafter with no model call at all.

**`unit_evidence` is checkable.** The agent quotes the text it read a unit
from and says `INFERRED` when it guessed. `unit_evidence_problems` sends back
a proposal that asserts a unit with nothing behind it. A claim is not
evidence.

**Everything is read as text.** `dtype=str`, then one explicit conversion
under the schema. Type inference is how a well identifier becomes a float and
a sample code becomes a date.

## The fixtures are the deliverable

`fixtures/` holds nine exports. The seven broken ones matter more than the
code that catches them, and each carries a `.expected.json` naming the
assertion that must fire.

| Fixture | Assertion | What it breaks |
| --- | --- | --- |
| `excel_mangled.csv` | 2 | Excel turned sample codes and concentrations into dates, in the `1-Mar` form. |
| `transposed_plate.csv` | 5 | Rows where the other instrument wrote columns. The chapter's failure account. |
| `shifted_labels.csv` | 5 | Every label moved one position. Structurally perfect, entirely wrong. |
| `unit_collision_uM.csv` | 3 | Valid alone. Collides on merge with its nanomolar partner. |
| `unit_collision_nM.csv` | 3 | The partner. |
| `extra_column.csv` | 3 | A numeric field with no unit, added by a software update. |
| `percentage_as_fraction.csv` | 4 | Viability on the wrong scale by a factor of a hundred. |

`transposed_plate.csv` is the one to look at. Every value is in range, every
type is right, the file is beautiful, and it passes the schema completely. A
true transpose turns a two by three plate into a three by two one, so it
writes a `C` row the plate never had. Assertion five catches it in about a
second, and in the chapter's account nobody ran it.

**Every real file that breaks your pipeline becomes a fixture before you fix
the bug.** That is the rule this directory exists to continue. When an export
defeats you, add it here with a `.expected.json` first, watch it fail, and
only then go and fix the code.

## The six assertions

In `assertions.py`, each raising a named exception carrying its number,
because "the pipeline threw" is not a diagnosis.

1. Row conservation. Wells in equals rows out, allowing for declared melts.
2. No silent nulls. The delta must be zero unless declared.
3. Unit declared for every measured column.
4. Range plausibility, read out of the schema rather than restated.
5. Identifier integrity. Every well matches the plate map.
6. Determinism. The same input produces byte-identical output.

`pipeline.run` applies them in that order, with the schema between four and
five. That placement is deliberate: a transposed plate must pass the schema
before assertion five catches it, which is the whole point of the example.

## Assertion 4 reads the schema, it does not copy it

`validate.BOUNDS` is derived from `schema.TidyReadings` by introspection at
import. Nothing restates a bound. A second copy of the numbers would drift the
day somebody widened one, leaving an assertion checking a range the schema no
longer declares.

The bounds encode what is physically possible, not what is tidy. Viability
starts at minus 0.2 because a treated well legitimately reads below blank, and
a schema that forbids real data is a broken schema: it gets switched off by
the first person it inconveniences, and then nothing is checked at all.

## Run it

```
pytest builds/05-wrangler/tests/
```

No API key, no network. The proposal step runs against a stub.

To wrangle a file of your own, from inside `builds/05-wrangler/`:

```python
from pipeline import load_mapping, run
from assertions import Expectation

mapping = load_mapping("mappings/qpcr_long.yaml")
result = run("fixtures/qpcr_long.csv", mapping, Expectation(wells=6, targets=1))
print(result["frame"])
```

For an export with no mapping yet, call `propose_mapping`, read what came
back, satisfy yourself about the `unit_evidence`, then set `approved_by` and
`approved_at` and save it under `mappings/`. Nothing transforms until you do.

## Known gaps, recorded rather than hidden

Two properties of the printed material are worth knowing before you rely on
this build. Both are in `HANDOFF.md` with the evidence.

The printed schema puts no pattern on `compound`, so a mangled compound code
on its own is not caught by anything here. `excel_mangled.csv` is detected
because Excel also ate the concentration in the same rows.

The printed `apply_mapping` reads with `dtype=str` but does not pass
`keep_default_na=False`, so a compound literally named `NA` becomes null
despite the chapter's instruction to read everything as text. No fixture uses
that name, which is itself a workaround rather than a fix.

## What is not here

No plate design, which is Build 06. No analysis. The wrangler produces a tidy
table and stops.
