# Fixture corpus for Build 07

## Everything here is fabricated

**No protocol in `source_protocols/` is real.** Every DOI is invented, every
title, every methods section, every number in them. No sentence is taken,
quoted or paraphrased from a real paper. Nothing here should be cited, quoted,
or read as a statement about how any assay is actually run.

**No cell line in `target_lines.json` is real.** The four names, the four
RRIDs, the doubling times, the serum concentrations, the solvent tolerances,
the passage ceilings and the assay interference flags were all written for this
repository. `HEP-3355` does not exist and neither does its resazurin problem.

This warning is not boilerplate. A file of realistic-looking cell line records
with plausible doubling times is exactly the sort of thing that gets scraped
and reused, and a doubling time is the input this build multiplies a seeding
density by. A fabricated one produces a confidently wrong plate.

## Why the identifiers look the way they do

The DOIs all use the `10.5555` prefix, which is the registered test prefix and
resolves to nothing. The RRIDs run from `CVCL_9901` to `CVCL_9904`, above the
range Cellosaurus has issued, so a reader who pastes one into a browser gets
nothing rather than somebody else's cell line. The convention is the one Build
03 uses for its PMIDs, and for the same reason.

## What each file is for

### `source_protocols/`

| File | What it states |
| --- | --- |
| `full_disclosure.md` | All six Table 6.2 parameters, each with a quotable value. The baseline. |
| `omits_density_and_endpoint.md` | Says nothing about seeding density or time to readout, and carries no RRID for its own line. Two absences and an unverifiable identity. |
| `ambiguous_density.md` | Says "an appropriate density" and "low passage cultures". Gestures, not statements. |

### `target_lines.json`

Four records. `GBM-4471` is the line the three protocols were run in, so it
doubles as the source lookup: adapting a protocol to its own line should
change nothing. `NSC-8810` doubles every 55 h against the source's 22 h, which
is the appreciably slower case the seeding density arithmetic exists for.
`HEP-3355` flags resazurin, so a protocol using that chemistry needs a person.

### `expected/`

One file per source and target pairing, twelve in all, naming which of the four
lists each of the six parameters must appear in. These were written out from
the protocol text and the line records by hand, not generated from the adapter.
An expectation derived from the code it checks asserts nothing.
