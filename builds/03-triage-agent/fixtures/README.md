# Fixture corpus for Build 03

## Everything here is fabricated

**No record in `corpus/` is real.** Every PMID is invented, every title, every
abstract, every journal name and every result in them was written for this
repository. No abstract text is taken, quoted or paraphrased from a real
paper, and none of the numbers is a real measurement. Nothing here should be
cited, quoted, or read as a finding about any drug, cell line or laboratory.

This warning is not boilerplate. This book is partly about fabricated
citations and the harm they do, and a corpus of realistic-looking abstracts
sitting in a public repository is exactly the sort of thing that gets scraped,
quoted and believed. If you are reading this file without the surrounding
chapter, that is the context you were missing.

The identifiers run from `99000001` to `99000061`. Eight digits beginning with
99 sit far above the range PubMed has issued, so they cannot collide with a
real record today, and a reader who pastes one into PubMed gets nothing rather
than somebody else's paper.

## What the corpus is for

Sixty-one records that Build 03 screens against
`criteria/repurposing_v3.yaml`. They exist so the tests run with no network
and no API key, and so the screening behaviour can be checked against a known
answer.

Each file in `corpus/` is a cache entry in the shape the cache layer writes:
the payload `fetch_abstract` returns, plus a SHA-256 taken over it. Dropping
these into the cache directory is what lets a run proceed entirely offline.

## Composition

| Label | Count | Share |
| --- | --- | --- |
| include | 9 | 14.8 per cent |
| exclude | 50 | 82.0 per cent |
| flag | 2 | 3.3 per cent |

Prevalence of 14.8 per cent is higher than a real screening corpus, where one
or two per cent is common, and low enough that the metrics behave the way
Chapter 4 describes.

The fifty exclusions are spread across all four routes out of the criteria
rather than piled onto one, because a corpus that fails in a single way tests
a single thing:

| Route | Count |
| --- | --- |
| `review` fires: reviews, editorials, comments, conference abstracts | 12 |
| `no_drug` fires: no qualifying drug treatment | 12 |
| `liver_model` fails: not a human liver model | 13 |
| `numeric_endpoint` fails: no IC50, EC50 or percentage viability | 13 |

Abstracts run from 80 to 137 words, except `99000004`, which is thirteen
words on purpose.

## The seven designed records

Four were asked for by the spec and three more added on the same principle.
Each exists to be got wrong by a plausible but careless screen, and
`gold.json` carries the reasoning for each under `notes`.

| PMID | Answer | The trap |
| --- | --- | --- |
| `99000001` | exclude | HEK293 transfected with a liver transporter. Dense with *hepatic*, *pravastatin*, *uptake*, and reports clean IC50 values. `liver_model` names HEK293 as not qualifying. |
| `99000002` | include | Primary human hepatocytes. Missed by any screen matching only the three immortalised lines. The mirror of `99000001`: one criterion, opposite directions. |
| `99000003` | flag | IC50 values, but the cell model is deferred to an earlier paper and never named. Unevaluable, which `on_ambiguity` says to flag, not to exclude. |
| `99000004` | flag | One sentence. Too short to screen, which is the property under test. |
| `99000012` | exclude | HepG2, drug treatment, but the result is only "significantly reduced viability". The reverse of `99000003`: here the criterion **can** be judged and fails. |
| `99000013` | exclude | HepG2 with an IC50, but a crude unfractionated botanical extract. `no_drug` fires: crude extracts do not qualify. |
| `99000061` | include | The same species and the same cell line as `99000013`, standardised to 78.4 per cent silibinin, quantified, and dosed as constituent equivalents. `no_drug` admits it. |

`99000013` and `99000061` are a matched pair. Same plant, same cell line, both
with a clean IC50. They differ in exactly one property, whether the active
constituent is named and quantified, and under the `no_drug` clause that one
property decides the verdict in opposite directions. A screen that reads
"extract" and stops gets one of the two wrong whichever way it stops.

`99000039` and `99000040` deserve a mention too. Both are liver models with
clean IC50 values, and both are excluded, because one is primary **rat**
hepatocytes and the other a **murine** line. The criterion names human models
only. They are a third form of the same trap.

## A note on the drug clause

Read the `no_drug` clause in `criteria/repurposing_v3.yaml` before judging
either extract record. It defines a drug as a defined chemical entity given at
a stated concentration, admits approved therapeutics and tool compounds alike,
rejects crude and unfractionated extracts, and admits a standardised extract
only where its active constituent is named and quantified.

That definition is why `99000013` and `99000061` both have an answer. An
earlier draft of the criteria left the word undefined, and `99000061` was the
case that exposed it: two screeners could have read it in opposite directions
in good faith, with nothing in the file to settle the argument. Both records
are kept in the corpus so that a future edit weakening the clause fails
visibly rather than quietly.

## Regenerating

Do not. These files are written once and committed. They are the deliverable,
not scaffolding: the screening behaviour is only as good as the corpus it is
judged against, and a regenerated corpus would silently invalidate every
recorded result.
