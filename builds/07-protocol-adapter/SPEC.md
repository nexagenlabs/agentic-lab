# SPEC: Build 07, protocol-adapter

**Chapter 6, "Protocol Agents", second half.**

## Purpose

Adapt a published protocol to a different cell line, and emit a diff naming
every parameter that changed, every parameter carried over unchanged, and every
parameter the source never stated.

The insight that shapes the build: **the adapted protocol is not the product.
The diff is.** The chapter's failure account is an adapter that changed the
concentrations it was asked about and silently kept the seeding density and
endpoint it was not, producing confluent wells, a compressed dynamic range and
an IC50 roughly twofold wrong, with every check passing.

## Files and printed listings

| Listing | File |
|---|---|
| `03_adaptation_models` | `models.py` |

Currently `mode: skip` in the manifest. Change it to `exact` when the build
exists.

## Behaviour required

**Enumerate the silence.** `carried_over_unchanged` and `not_stated_in_source`
are required, non-empty-or-explicitly-empty lists. An adapter that reports only
what it changed lets a reader walk into everything it did not consider. This is
the general principle the chapter draws and it applies to every agent in the
book.

**The six parameters are mandatory.** Every parameter in Table 6.2 must appear
in exactly one of the four lists: seeding density, incubation to endpoint,
solvent tolerance, passage number range, serum concentration, readout
chemistry. Silence about any of them is an error, not a default. Implement this
as a validator on `Adaptation`, not as a prompt instruction, so it cannot be
talked out of it.

**Doubling time drives seeding density.** The adapter takes a target line
record carrying doubling time and, if the source states its own line's doubling
time or you have it in a lookup, must either propose a scaled density with the
arithmetic shown, or place seeding density in `requires_human_decision`. It
must never carry it over silently. Arithmetic in Python, as always.

**The reporting standard is the target.** The output maps onto Good In Vitro
Reporting Standards categories: cell source and identity, quality control,
materials, culture conditions, design, analysis, data availability. Emit
`adaptation_report.md` organised that way, so a reader can see which categories
the source protocol left empty. That absence is the useful output.

**Identity again.** The target line record carries an RRID, as in Build 06.

## Fixtures

- `fixtures/source_protocols/`, three fabricated published protocols in
  markdown, with front matter giving a fabricated DOI. One states its
  parameters fully, one omits seeding density and endpoint, and one states them
  ambiguously ("cells were seeded at an appropriate density").
- `fixtures/target_lines.json`, four cell line records with RRID and doubling
  time, at least one appreciably slower than the sources.
- `fixtures/expected/`, for each source and target pairing, the parameters that
  must appear in each of the four lists.

Fabricate everything. State that plainly in `fixtures/README.md` as Build 03
does.

## Gate: `pytest builds/07-protocol-adapter/tests/`

**`test_every_table_parameter_is_classified`**
For every source and target pairing, assert all six parameters appear in
exactly one list. Assert a parameter appearing in none, or in two, raises.

**`test_silence_is_reported_not_defaulted`**
Adapt the protocol that omits seeding density and endpoint. Assert both appear
in `not_stated_in_source`, and that neither is silently given a value.

**`test_carryover_is_explicit`**
Adapt to a target with a different doubling time. Assert seeding density is
either changed with a rationale or placed in `requires_human_decision`, and
assert it never appears in `carried_over_unchanged` for that pairing. This is
the chapter's failure account, as a test.

**`test_ambiguous_source_does_not_invent`**
Adapt the protocol saying "an appropriate density". Assert it is treated as not
stated rather than interpreted.

**`test_report_names_empty_categories`**
Assert `adaptation_report.md` lists the reporting categories the source left
empty, rather than omitting them.

No test may touch the network.

## Report back

Against the five points in `CLAUDE.md`, plus: for the ambiguous protocol, what
the adapter did with "an appropriate density", and whether it required
prompting or the validator to stop it inventing a number.
