# Reference resolution

Companion to `references_report.md`, which is machine-generated. This file
records what a human decision still hangs on. Produced by running
`tools/verify_references.py` against `references/references.yaml` until the
output was byte-identical between consecutive runs.

Two passes so far. The first checked the list as it stood. The second found
that the list was the wrong list.

---

## Pass 2 — reconciling against Appendix D

Appendix D carries 74 entries. `references.yaml` held 47. Twenty-two of the
missing entries were named and have been added; **five are still unaccounted
for** (47 + 22 = 69, not 74). That arithmetic is now a failing test rather than
a note, see *The manifest and the test* below.

### Counts

| Status | Pass 1 start | Pass 1 end | Pass 2 end |
| --- | --- | --- | --- |
| CONFIRMED | 24 | 24 | **40** |
| MISMATCH | 0 | 0 | 0 |
| UNRESOLVED | 0 | 0 | 0 |
| UNSOURCED | 1 | 1 | **2** |
| SKIPPED | 22 | 22 | **27** |
| **total** | 47 | 47 | **69** |

Sixteen of the twenty-two new entries resolved to a DOI and confirmed against
Crossref on the first run. Every title, author, venue, volume, page range and
year written into those sixteen was copied from the Crossref record, not
recalled — so each one is checked by the tool that reads this file.

### DOIs added

All sixteen resolved directly against Crossref before being written, and all
sixteen come back CONFIRMED.

| Entry | DOI | Work |
| --- | --- | --- |
| `cochrane_handbook_v6` | `10.1002/9781119536604` | Cochrane Handbook for Systematic Reviews of Interventions, Wiley 2019 |
| `loewe1926combination` | `10.1007/BF01952257` | Loewe & Muischnek, *Über Kombinationswirkungen*, 1926 |
| `bliss1939joint` | `10.1111/j.1744-7348.1939.tb06990.x` | Bliss, *The toxicity of poisons applied jointly*, 1939 |
| `fuentealba2023synergysoftware` | `10.3390/ijms24119705` | *Mind the Curve*, IJMS 2023 |
| `givrest2025` | `10.14573/altex.2507041` | GIVReSt guidance, ALTEX 2025 |
| `ralston2026cellauth` | `10.3389/fcell.2026.1843943` | Cell line authentication, Front. Cell Dev. Biol. 2026 |
| `plewczynski2011docking` | `10.1002/jcc.21643` | Seven docking programs, 1,300 PDBbind complexes |
| `scardino2023alphafolddocking` | `10.1016/j.isci.2022.105920` | AlphaFold models, 22-target screening benchmark |
| `berman2000pdb` | `10.1093/nar/28.1.235` | Berman et al., The Protein Data Bank |
| `chang2022replicable` | `10.1561/104.00000053` | Chang & Li, Critical Finance Review 2022 |
| `brodeur2026reproducibility` | `10.1038/s41586-026-10251-x` | 110 articles, Nature 652:151–156 |
| `iarygina2026hcirepro` | `10.1145/3772318.3791129` | CHI 2026 reproducibility study |
| `hornung2026barriers` | `10.1098/rsos.252489` | RSOS 2026 reproducibility guidance |
| `bhattacharyya2023fabricated` | `10.7759/cureus.39238` | Bhattacharyya et al., Cureus 2023 |
| `topaz2026lancetaudit` | `10.1016/S0140-6736(26)00603-3` | Lancet fabricated-citation audit |
| `becker2026problemdrift` | `10.18653/v1/2026.findings-eacl.268` | *Stay Focused: Problem Drift in Multi-Agent Debate* |

Six more were resolved to a real work that has no Crossref DOI to pin, so they
are SKIPPED and verified by URL or arXiv ID instead:

- `ghostcite2026` — arXiv 2602.06718, submitted 6 February 2026
- `phantom_references_2026` — arXiv 2607.00738, submitted 1 July 2026
- `pandera_docs` — <https://pandera.readthedocs.io/en/stable/>, live
- `gaddum1940pharmacology` — 1940 OUP textbook, predates DOIs
- `nasa_mco_mib_1999` — 1.4 MB PDF on `llis.nasa.gov`, live
- (plus `alphafold3_ligand_eval`, which resolved to nothing — below)

### Still unsourced

**`alphafold3_ligand_eval` — new, and it cannot be closed from here.**

Appendix D gives only "Evaluation of AlphaFold 3 for protein-ligand prediction
(2025 to 2026)". Unlike every other description in the list, this one does not
narrow to a single paper. Searching the finding returns at least four distinct
2025–2026 evaluations, each reporting something different: a stereochemistry
critique of AlphaFold 3 and Boltz-1 ligand geometry, a virtual-screening
assessment of AlphaFold3-like models including Protenix and Boltz-2, a broad
AlphaFold3-in-drug-discovery assessment, and a pose-generation benchmark on the
ASAP Antiviral Challenge 2025.

Whichever AlphaFold 3 number Chapter 7 quotes rests on this entry. Either
identify the paper the number came from, or soften the sentence back to the
AlphaFold 2 evidence in `scardino2023alphafolddocking`, which is sourced and
which measured 22 targets. Note that the sourced paper is explicitly AlphaFold
2 — its AlphaFold Database snapshot is November 2022 — so it cannot stand in
for an AlphaFold 3 claim without the claim changing.

**`practitioner2026_coordination` — unchanged from pass 1.**

Chapter 12 orchestration overhead. Nothing sources it. You already removed the
950ms-against-500 and 29,000-tokens-against-10,000 figures and labelled the
eighty per cent claim as one team's report. I did not go looking for something
close enough to attach, because a plausible near-match is the failure, not the
fix.

### Contradictions found in pass 2

These are findings about what the appendix claims, not gaps.

1. **The Lancet entry understates its own source by half a million papers.**
   Appendix D says "two million papers". The paper's *title* says 2·5 million,
   and the audit covered 2.47 million open-access biomedical papers and 125.6
   million references. A reader checking the citation finds a different number
   in the title than in the book. Fix the prose.

2. **GhostCite's "forty research domains" is not in the paper's abstract.** The
   abstract confirms thirteen models and a hallucination range of 14.23 % to
   94.93 %, but describes **2.2 million citations from 56,381 papers in AI/ML
   and Security venues, 2020–2025**. It does not say forty domains. "Forty
   domains" came only from a secondary summary — as did a figure of 375,000
   citations, which is also wrong. If Chapter 10 says forty domains, that
   number needs checking against the full text or removing. I read the abstract
   only, so treat everything I report about this paper as unverified against
   the body.

3. **Chang & Li exists twice, with different subtitles.** The 2015 Federal
   Reserve working paper says "Usually Not" (`10.17016/FEDS.2015.083`); the
   2022 *Critical Finance Review* article says "Often Not"
   (`10.1561/104.00000053`). Both resolve. Appendix D gives no year, so it
   picks neither. Citing one venue beside the other's subtitle is the partial
   attribute corruption Chapter 10 is about. I entered the published 2022
   version; confirm that is the one Chapter 9 read, because the replication
   counts are reported differently between them.

4. **The docking correlation range needs re-reading.**
   `builds/08-dock-loop/README.md` gives "0.10 to 0.38 across seven programs".
   Plewczyński et al.'s own summary of that result is that the best correlation
   is around 0.4. Compatible, but not the same statement. Read the correlation
   table before printing the range. Separately, the seventh program is
   **AutoDock, not AutoDock Vina**, so the "minus 0.18 for Vina" figure in the
   same paragraph is from a different benchmark and remains unsourced.

5. **The AlphaFold screening benchmark is AlphaFold 2.** `scardino2023…` used
   an AlphaFold Database snapshot from November 2022. If Chapter 7 reads it as
   a statement about AlphaFold generally, that needs narrowing.

6. **One appendix entry is three documents.** "Good In Vitro Reporting
   Standards, with GCCP 2.0 and OECD guidance" bundles GIVReSt (ALTEX 2025,
   `10.14573/altex.2507041`), GCCP 2.0 (ALTEX 2020, `10.14573/altex.2007091`)
   and the OECD GIVIMP guidance, which has no Crossref DOI. Splitting them
   into three entries changes the appendix count, so it is your call — but as
   one entry it cannot be cited precisely.

7. **`ralston2026cellauth` is a 2026 paper reporting 2024 and 2025 data.** The
   Chapter 6 numbers match exactly (4.7 % misidentified in 2024, 2.4 % in
   2025, from 1,893 samples at one commercial STR service), but the citation
   year and the data years differ, and the sentence should say which it means.
   The figures are one provider's submitted samples, not a population
   estimate, which the Build 06 README already gets right.

8. **`becker2026problemdrift` was identified on a term, not a title.** "Problem
   drift" is that paper's coinage and the year matches, which is why it is
   entered rather than left unsourced. But a near neighbour exists — *Agent
   Drift: Quantifying Behavioral Degradation in Multi-Agent LLM Systems Over
   Extended Interactions*, arXiv 2601.04170 — whose title matches the
   appendix's words "extended interactions" more closely while using a
   different term. If Chapter 10 quotes a drift figure, check which paper it
   came from. This repository quotes no drift percentage anywhere, so nothing
   here settles it.

9. **`nasa_mco_mib_1999`'s title was not machine-verified.** The URL is live
   and NASA-hosted, but the PDF's only embedded title is `MCO Report83.doc`,
   and the cover page could not be extracted. The title in the entry is the
   appendix's wording, not a transcription. Somebody should read the cover
   once.

10. **`pandera_docs` cites documentation with no version.** The stable docs
    banner reads 0.32.0; `REVIEW.md` records this repository pinning 0.33.0.
    A documentation citation naming no version cannot be checked later by
    anyone. Record the version the book was written against.

11. **The Cochrane Handbook "version 6" is ambiguous.** The DOI pins the Wiley
    printed edition of 20 September 2019. The online handbook at
    `training.cochrane.org/handbook` is continuously revised and is past 6.0,
    so a bare "version 6" does not identify what was read. Cite the 2019
    edition or the online version with its point release and an access date.

### A change to the verification tool

Two kinds of entry were being sent to a Crossref title search that cannot
succeed, which is the same mistake the script already documents for arXiv
preprints — a search that cannot find the work reports a mismatch the tool
invented.

- `kind: report` now skips to URL verification, alongside standards and
  regulations. A NASA mishap report has no DOI.
- `kind: book` **with no DOI** now skips too. Gaddum 1940 predates DOIs; a
  title search on the single word "Pharmacology" matches an unrelated modern
  work. Books that carry a DOI, like the Cochrane Handbook, still resolve by
  it.

---

## The manifest and the test

`references/appendix_d.manifest.yaml` plus
`tests/test_appendix_d_manifest.py`. The manuscript is outside the repository,
so the manifest is a hand transcription of the printed appendix and is the
weakest link by construction. The shape is chosen around that.

**A count stated separately from the list.** The manifest names `count: 74` as
a bare number rather than deriving it from `len(entries)`. Derived, it would be
vacuous — a row deleted from both files at once would pass. Stated on its own
it is an independent witness, and it is the assertion that would have caught
the original drift on the day it happened.

**Set equality in both directions.** The original bug was one-directional:
`references.yaml` was a subset of the appendix, and the tool reported green on
the subset. A containment check in the convenient direction would have passed
for the whole first draft. The test asserts both `appendix - yaml` and
`yaml - appendix` are empty, and reports them separately, because the two
failures mean different things.

**A short identifying phrase per entry, anchored back into the entry.** The
phrase is what lets a person find the row on the printed page. The test
requires it to appear in that entry's id, title or note in `references.yaml`.

That last one is the non-obvious part, so: I did **not** assert that the phrase
matches the entry's title. Many of these entries were descriptions of findings,
and resolving them replaces the description with the real title — "Comparative
assessment of seven docking programs" becomes "Can we trust docking results?".
Asserting title-equals-phrase would force the two lists back into agreement in
exactly the wrong direction, by corrupting the resolved title back into the
description. Instead the appendix's wording is quoted verbatim in the entry's
note, so **an entry cannot be resolved without recording what the appendix says
about it**, and the trail from printed page to resolved paper survives. Three
entries had to have their notes amended to satisfy this; that is the invariant
doing its job.

Comparison is on words alone — lowercased, punctuation collapsed. A middle dot
for a decimal point, a tilde for "approximately", curly quotes and en dashes
all differ between a printed page and a retyped note without changing which
entry is named, and a test that failed on those would be retrained into
uselessness inside a week.

**The test fails right now, on purpose.** 5 of 6 assertions pass. The count
assertion fails at 69 transcribed against 74 counted. Full suite: **134 passed,
1 failed**, and the one failure is this. Do not fix it by lowering the count to
69 — that would re-create the original bug with a green light on top. Either
five appendix entries have never been seen by this repository, or the count of
74 is wrong, or `references.yaml` holds entries the appendix does not. Only the
printed page settles which, and the docstring says so where the next person
will read it.

What the test cannot do: it cannot tell you the manifest is a faithful
transcription. Nothing inside the repository can, while the manuscript is
outside it. It can only stop the two lists that *are* here from drifting apart
again, and keep the drift already found visible until someone reads the page.

---

## Pass 1 — the original list

Kept for the record. Counts went 24/0/0/1/22 to 24/0/0/1/22: nothing moved,
which was the honest headline. Every entry Crossref could reach was already
confirmed by DOI, none by title search. The exposure was in the 22 SKIPPED
entries, which the tool does not check at all — it prints whatever URL the
entry carries, and **eleven of those URLs pointed at a homepage** rather than a
document (`https://www.fda.gov/` for a joint FDA/EMA paper,
`https://www.anthropic.com/` for a system card, `https://owasp.org/` for the
agentic Top 10, `https://eur-lex.europa.eu/` for a named regulation). All
eleven now point at the document, each fetched before it was written.

One DOI added: `ghareeb2025robin` → `10.1038/s41586-026-10652-y`. **Robin has
been published**: *Nature* 655:497–505, online 19 May 2026, and the published
title dropped the "Robin:" prefix. `kind` was deliberately left as `preprint`,
because flipping it to `article` makes the tool report CONFIRMED for a *Nature*
DOI sitting beside `venue: "arXiv"` and `year: 2025` — the exact corruption
Chapter 10 describes. Switching to the published version means editing title,
venue, volume, pages and year together, which is an author decision.

Other pass-1 findings, all still open:

- `anthropic_opus45_card` — URL fixed, but the 4.7 / 33.6 / 63.0 per cent
  injection figures remain **unverified**: the card is an 11.5 MB PDF, over the
  fetch limit, and secondary coverage does not reproduce the per-attempt
  breakdown. Needs one person opening it.
- `owasp_llm_top10` pointed at a legacy archive holding the **2023** list while
  claiming 2025. Fixed. A 2026 edition also exists, so which edition Chapter 8
  cites is a live choice.
- `patil_bfcl` is dated 2024; the leaderboard reads "Last Updated: 2026-04-12"
  and is at V4. Needs an access date.
- `cve_2026_22708` has a description where a title should be. The record is
  GHSA-82wg-qcm4-fp2w, "Terminal Tool Allowlist Bypass via Environment
  Variables", in Cursor before 2.3.
- Two title truncations: `anthropic_tools` is "…— with agents";
  `fda_ema_2026_principles` says "AI", not "artificial intelligence".

Confirmed against primary sources in pass 1: Gartner's "over 40 % … by end of
2027" (25 June 2025), and the Digital Omnibus — Regulation (EU) 2026/1744, in
force 27 July 2026, with both revised high-risk dates (2 December 2027 and
2 August 2028) matching.

---

## What a hostile reviewer can still say

That 27 of 69 entries are not verified by anything, only pointed at. True, and
structural: no Crossref check validates a CFR part, an OWASP list, a NASA
report or a vendor system card. What can be said back is that all 27 now point
at the document rather than a homepage, that the two that name findings instead
of works are flagged as such in the file and in a failing gate, and that the
list itself is now held against the printed appendix by a test rather than by
somebody's memory of having reconciled it once.

And the thing not to say back: that the list is complete. Five entries are
still missing and the test says so.
