# SPEC: Build 05, wrangler

**Chapter 5, "Data-Wrangling Agents for Omics, Imaging and Instrument
Exports".**

## Purpose

An agent that reads an unfamiliar instrument export, proposes a column mapping
for a human to approve, and then hands off to deterministic code that does the
transformation under a schema with declared units.

The design decision that carries the whole build: **the agent never touches a
number.** It supplies judgement about what a column means. Code supplies every
transformation, conversion and total. If you find yourself asking a model for
an arithmetic result, re-read this paragraph.

## Files and printed listings

| Listing | File |
|---|---|
| `01_profile` | `profile.py` |
| `02_mapping_models` | `models.py` |
| `03_apply_mapping` | `transform.py` |
| `04_pandera_schema` | `schema.py` |

All four are `mode: exact`. Note that `_sniff` in `profile.py` is referenced but
not printed; implement it so it returns `None` rather than raising, because
`csv.Sniffer` throws readily on real exports.

## Behaviour required

**Bounded input.** The agent sees the first fifteen lines and a shape summary,
never the whole file. This caps cost, caps context growth, and stops the model
forming opinions about values, which is precisely what we do not want.

**The mapping is data, and it is approved.** `apply_mapping` raises on an
unapproved mapping. That refusal is three lines and it is what makes the human
gate structural rather than procedural. Approved mappings are written to
`mappings/<instrument>.yaml` and reused deterministically thereafter, with no
model call at all.

**`unit_evidence` is required and must be checkable.** The agent records where
it saw a unit, quoting the text, and says explicitly when it inferred the unit
from values rather than reading it. A claim is not evidence.

**Units live in column names.** `conc_nM`, never `conc`. A merge that puts a
micromolar column beside a nanomolar one must produce a name collision your
code notices, not a silent thousandfold error.

**Everything is read as text.** `dtype=str` on the read, then explicit
conversion under the schema. Type inference is how a well identifier becomes a
float and a sample code becomes a date.

**Bounds encode what is physically possible, not what is tidy.** The printed
schema allows viability from minus 0.2, because a treated well legitimately
reads below blank. A schema that forbids real data is a broken schema.

## The six assertions

Implement all six from Table 5.2 in `assertions.py`, each raising a named
exception carrying which assertion failed:

1. **Row conservation.** Wells in equals rows out, allowing for declared melts.
   Rows may be removed with a logged reason; rows may never simply be absent.
2. **No silent nulls.** Count nulls before and after; require the delta to be
   zero unless declared.
3. **Unit declared for every numeric column.**
4. **Range plausibility per column**, from the schema.
5. **Identifier integrity.** Every well matches the plate map. This is the
   assertion the chapter's failure account says would have caught a transposed
   plate in one second, and it is the cheapest one on the list.
6. **Determinism.** The same input file produces byte-identical output,
   including column order.

## Fixtures: the most important part of this build

`fixtures/` holds instrument exports. The broken ones are the deliverable.

**Two clean exports**, in different shapes, both representing the same
experiment so a test can prove they converge:
- `plate_wide.csv`, wells as columns, a merged plate identifier above the
  header, three header rows before the data.
- `qpcr_long.csv`, one row per well per target, with a different well naming
  scheme.

**Seven broken exports**, each breaking exactly one thing, each with a
`.expected.json` naming which assertion must fire:
- `excel_mangled.csv`, sample codes converted to dates by Excel, in the
  `1-Mar` form the 2016 study found accounted for most conversions.
- `transposed_plate.csv`, rows where the other instrument wrote columns. This
  is the chapter's failure account. It must pass the schema and fail assertion
  five.
- `shifted_labels.csv`, every sample label moved by one position. Structurally
  perfect, entirely wrong.
- `unit_collision_uM.csv` and `unit_collision_nM.csv`, the same quantity in
  different units, which must fail on merge rather than concatenate.
- `extra_column.csv`, a field added by a software update, which strict mode
  must reject.
- `percentage_as_fraction.csv`, viability stored as 0.87 where the schema
  expects 87.

Write these yourself. Do not use real instrument data.

The rule the chapter states and this build should embody: **every real file
that breaks your pipeline becomes a fixture before you fix the bug.** Note that
in the README so the next person continues it.

## Gate: `pytest builds/05-wrangler/tests/`

**`test_row_conservation`**
Transform a fixture of known size; assert output rows equal wells times targets
exactly, and that any deviation is itemised in the manifest with a reason.

**`test_unit_collision_is_caught`**
Merge the two unit-collision fixtures; assert it raises rather than
concatenating. If it passes only because you remembered, it does not pass.

**`test_schema_rejects_known_corruptions`**
Run all seven broken fixtures; assert each is rejected and each reports which
assertion failed, matching its `.expected.json`.

**`test_transform_is_deterministic`**
Run the same input twice; assert byte-identical output including column order.
Non-determinism here means something iterates a set or reads a clock, and it
makes Chapter 9 impossible.

**`test_unapproved_mapping_refuses`**
Assert `apply_mapping` raises on a mapping with `approved_at` unset.

**`test_two_shapes_converge`**
Transform both clean exports; assert they produce the same tidy table.

No test may touch the network. Use a stubbed model client for the proposal
step.

## Out of scope

No plate design, which is Build 06. No analysis. The wrangler produces a tidy
table and stops.

## Report back

Against the five points in `CLAUDE.md`, plus: which assertion each broken
fixture fires, and whether any of the seven passes when it should not. A broken
fixture that slips through is more interesting than six that are caught.
