# Fixture corpus for Build 11

## Everything here is fabricated

**No DOI, PMID, journal, author, finding or record in this folder is real.**
`metadata.json` stands in for Crossref or PubMed: an identifier that is not in
its `records` map is one that does not exist, which is precisely what a
fabricated reference is. The identifiers are invented, and
`10.1234/jmtr.2021.0417` is not a registered DOI.

That warning matters more here than usual. This folder exists to make things
look convincingly real to a system that is trying to catch them.

## Most of what this build runs on is not in this folder

The red team measures the earlier builds, so it uses their committed fixtures,
read as files rather than imported:

| What | From |
|---|---|
| The screening corpus | `builds/03-triage-agent/fixtures/corpus/` |
| The broken exports | `builds/05-wrangler/fixtures/` |
| The plate design | `builds/06-plate-mapper/designs/tmz_na_u87mg.yaml` |
| Three of the six loop scripts | `builds/01-first-agent/fixtures/` |

Those fixtures arrive with `.expected.json` files somebody already argued
about, which is worth more than fixtures invented here to be caught. A red team
whose inputs were built alongside its checks is measuring its own consistency.

Four things had to be new, because nothing in the repository had them.

## `metadata.json`

Five records. Two of them exist to be mistaken for each other, and one,
`99000012`, is a paper about ambient laboratory temperature that shares a
journal with the OATP1B1 work. It is there so that a plausible PMID can resolve
to something real and entirely unrelated, which is the shape of a fabricated
citation that survives a "does this look right" check.

Each record carries a `findings` list. That is what makes
`citation_quote_supported` possible: the expensive check, where the identifier
resolves, the metadata agrees, and the sentence attributed to the paper is not
in it.

## `numeric/clean_export.csv`

Six rows, wells `A1` to `B3`, matching Build 05's `PLATE_MAP`. Headers
identical to `qpcr_long.csv` so Build 05's approved mapping applies unchanged.

The concentrations are deliberately low: 0.01, 0.1 and 1 micromolar, which
become 10, 100 and 1000 nanomolar. That is not decoration. Fault `numeric-01`
multiplies them by a thousand, and the whole point of the fault is that the
result stays inside the schema's declared bounds of 0 to 1e7. Build 05's own
`qpcr_long.csv` tops out at 10 micromolar, and a thousandfold error on that
lands exactly on the upper bound, where the fault would be caught by an
accident of arithmetic rather than missed on its merits. A fixture that made
the check pass for the wrong reason would be worse than no fixture.

## `loop/repeated_tool.json` and `loop/unachievable.json`

Two scripts in Build 01's own fixture format, because Build 01 had nothing of
this shape.

`repeated_tool.json` is the loop family's silent miss and the more interesting
of the two. The model calls the same tool with identical arguments four times
and then answers. Every call is valid, every call is allowed, the run returns
COMPLETE with an answer, and not one of Build 01's four orchestration checks
has anything to say. The cap was never reached, no tool failed, no write was
attempted. It is a loop pathology that terminates successfully.

`unachievable.json` is a task with no reachable completion state: the model
tries to record its finding, the write gate refuses because approval arrives
out of band and none ever does, and the cap is what stops it.

## `identity` records

Defined in `catalogue.py` rather than as a file, because they are four
variations on three papers and the variation is the content. A preprint and its
published version. One paper under a DOI in one place and a PMID in another.
A title differing only in whitespace and case.

None of them share an identifier, which is the entire point: Build 03's
deduplication is correct, and correct deduplication on identifiers counts these
as separate papers.
