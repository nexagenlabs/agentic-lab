# Reference resolution pass

Companion to `references_report.md`, which is machine-generated. This file
records what a human decision still hangs on. Run against
`references/references.yaml` with `tools/verify_references.py`, three
consecutive runs, byte-identical output on the last two.

## Counts, before and after

| Status | Before | After |
| --- | --- | --- |
| CONFIRMED | 24 | 24 |
| MISMATCH | 0 | 0 |
| UNRESOLVED | 0 | 0 |
| UNSOURCED | 1 | 1 |
| SKIPPED | 22 | 22 |

The counts did not move, and that is the honest headline. Every entry the
Crossref check can reach was already confirmed by DOI before this pass — all
24 of them, none by title search. The exposure the reviewer named is not in
the CONFIRMED set and never was. It is in the 22 SKIPPED entries, which the
tool does not verify at all; it declares them out of scope and prints whatever
URL the entry carries.

Eleven of those URLs did not locate the document they claimed. That is what
changed here. `https://www.fda.gov/` was standing in for a joint FDA/EMA
document, `https://www.anthropic.com/` for a system card, `https://owasp.org/`
for the agentic Top 10, `https://eur-lex.europa.eu/` for a named regulation.
A reviewer following those links reaches a homepage, which reads exactly like
a citation nobody checked. Each one now points at the document itself, and
each replacement URL was fetched and returned that document.

## DOIs added

One, and it is not the routine kind.

**`ghareeb2025robin`** — added `doi: 10.1038/s41586-026-10652-y`.

Resolved directly against Crossref: `type: journal-article`, container
*Nature*, volume 655, pages 497–505, published online 19 May 2026, first author
Ghareeb. The entry cites the arXiv preprint. **The work has been published, and
the published title dropped the "Robin:" prefix** — Crossref returns
"A multi-agent system for automating scientific discovery".

`kind` was deliberately left as `preprint`, so the tool still reports this
SKIPPED and does not resolve the new DOI. Flipping it to `article` makes the
tool report CONFIRMED, because the title similarity clears the threshold and
the year gap is only one — and it would be confirming a *Nature* DOI sitting
beside `venue: "arXiv"` and `year: 2025`. That is the partial attribute
corruption Chapter 10 describes and that `huang2026biomni` already carries a
warning about. A green tick on it would be worse than the current silence.

Switching to the published version means editing title, venue, volume, pages
and year together. Yours to make; the DOI is recorded in the entry so it is
not lost either way.

No other SKIPPED entry can take a DOI. Checked and confirmed absent for
`mitchener2025bixbench` (2503.00096) and `mas_vs_sas_2025` (2505.18286) —
both still arXiv-only, no published version, and arXiv registers with DataCite
rather than Crossref, so pinning an arXiv DOI would manufacture a failure. The
regulations, standards, CVEs and vendor documentation have no DOIs to find.

## Still unresolved, and the claim each one holds up

**`practitioner2026_coordination` — UNSOURCED, and it should stay that way.**

Supports the Chapter 12 orchestration-overhead passage. You already softened
this: the 950ms-against-500 and 29,000-tokens-against-10,000 figures are out,
the eighty per cent claim is labelled as one team's report, and the shape of
the finding is attributed to practitioner experience rather than measurement.
I found nothing that sources it. I did not look for something close enough to
attach, because a plausible near-match is the failure mode, not the fix. The
entry names a finding, not a work; the gate should keep failing on it.

**`anthropic_opus45_card` — URL now correct, numbers still unverified.**

Supports the Chapter 8 injection figures of 4.7, 33.6 and 63.0 per cent at
one, ten and one hundred attempts. The card is real, dated November 2025, and
`https://www.anthropic.com/claude-opus-4-5-system-card` now resolves to it
(11.5 MB PDF). I could not read the PDF — over the fetch size limit — and
secondary coverage does not reproduce the per-attempt breakdown. **The three
numbers remain unconfirmed by me.** They need one person opening that PDF.
Your existing note is right that the scoping to model, harness and attack
suite matters as much as the numbers.

**`gartner2025agentic` — claim confirmed.** The press release of 25 June 2025
is titled "Gartner Predicts Over 40% of Agentic AI Projects Will Be Canceled by
End of 2027". The chapter's "more than forty per cent cancelled by end of 2027"
matches the primary source. The URL 403s to a scripted client, which is bot
blocking rather than a dead link; it loads in a browser.

**`eu_digital_omnibus` — claim confirmed, and it now has a number.** This is
Regulation (EU) 2026/1744, of 8 July 2026, published in the OJ on 24 July and
in force 27 July 2026, which matches your note. Both revised high-risk dates
check out against the primary text: 2 December 2027 for stand-alone high-risk
systems, 2 August 2028 for high-risk systems embedded in products. The entry
title is a description rather than the regulation's name; the real name is
long, but it now has an ELI URL that pins it.

## Contradictions and stale claims found

These are findings, not gaps.

1. **Robin is published.** Covered above. The entry describes a preprint that
   has been a *Nature* paper since May 2026, under a different title.

2. **`owasp_llm_top10` pointed at the wrong edition.** The old URL still loads,
   which is why it survived earlier passes, but it is now a legacy archive
   carrying the 2023 v1.1 list and a notice that development moved to the
   GenAI Security Project. A reader checking the entry's 2025 claim would have
   found a 2023 list. Fixed. Separately: a 2026 edition exists, published
   4 August 2026, so which edition Chapter 8 cites is now a live choice.

3. **`patil_bfcl` is dated 2024 and the leaderboard is at V4.** The page reads
   "Last Updated: 2026-04-12". If Chapter 2 quotes figures off it, the year
   should be the year they were read, and an access date belongs in the entry.
   The page also hyphenates itself "Function-Calling"; the entry does not.

4. **`cve_2026_22708` has a description where a title should be.** The vendor
   advisory is GHSA-82wg-qcm4-fp2w, "Terminal Tool Allowlist Bypass via
   Environment Variables", and the product is Cursor before 2.3: shell
   built-ins such as `export` and `unset` ran in Auto-Run allowlist mode
   without appearing in the allowlist, so injection could poison `PATH` or
   `LD_PRELOAD` and turn an already-approved command into arbitrary execution.
   The entry says "an agentic coding assistant". This is precisely the shape
   the reviewer objected to, in an entry that turns out to be entirely real.

5. **Two title truncations.** `anthropic_tools` is "Writing effective tools for
   agents — with agents" (11 September 2025); the entry drops the tail.
   `fda_ema_2026_principles` titles itself "Guiding principles of good AI
   practice in drug development" (14 January 2026); the entry expands AI to
   "artificial intelligence". Neither is fabrication. Both are the kind of
   drift a hostile reviewer will call fabrication, so both are worth closing.

## The reviewer's two examples are not in this file

This matters more than anything above, so it is last where it will be read.

The reviewer named two entries:

- "Comparative assessment of seven docking programs across approximately
  1,300 protein-ligand complexes"
- "Benchmark of citation hallucination rates across thirteen models and forty
  research domains (2026)"

**Neither exists in `references.yaml`, and neither ever has** — no match in the
file, and no match anywhere in the git history of `references/`. The 47 entries
here are not the same list as the Appendix D the reviewer read. Either the
manuscript's appendix carries entries this file never mirrored, or the reviewer
paraphrased. Worth resolving before print, because this file is what the CI
gate checks and the appendix is what ships.

Both descriptions resolve to real work. Offered for you to add or not; I have
not added them, because they are not entries in this list and Appendix D is
not mine to edit.

**Seven docking programs, ~1,300 complexes** —
`10.1002/jcc.21643`, verified against Crossref: Plewczyński, Łaźniewski,
Augustyniak and Ginalski, "Can we trust docking results? Evaluation of seven
commonly used programs on PDBbind database", *Journal of Computational
Chemistry* 32:742–755. Seven programs (Surflex, LigandFit, Glide, GOLD, FlexX,
eHiTS, AutoDock) on 1,300 complexes from PDBbind 2007. The match on "seven"
and "1,300" is exact.

One thing to check against it. `builds/08-dock-loop/README.md` says "Score to
affinity correlations run from 0.10 to 0.38 across seven programs on roughly
1,300 complexes". The paper's own summary of that result is that the best
correlation is around 0.4. That is compatible with a 0.10–0.38 range but is not
the same statement, and 0.38 against "about 0.4" is close enough to be a
rounding or close enough to be a different table. Read the paper's correlation
table before printing the range. Note also that AutoDock, not AutoDock Vina, is
the seventh program, so the "minus 0.18 for Vina" figure in the same paragraph
is from some other benchmark and still has no source.

**Citation hallucination across thirteen models and forty domains** —
GhostCite, arXiv 2602.06718, "GhostCite: A Large-Scale Analysis of Citation
Validity in the Age of Large Language Models". 13 LLMs, 40 domains, 375K
citations, hallucination rates from 14 to 95 per cent. arXiv-only, so no
Crossref DOI to pin; it would enter as `kind: preprint` with an `arxiv` field
and be SKIPPED, like the others. I have not verified the 14–95 per cent range
against the paper itself, only against search results, so treat the numbers as
unchecked until someone reads it. If Chapter 10 quotes a figure from it, that
figure needs reading off the PDF.

## What a hostile reviewer can still say

That 22 of 47 entries are not verified by anything, only pointed at. That is
true and it is structural: no Crossref check can validate a CFR part, an OWASP
list or a vendor system card. What can be said back is that all 22 now point at
the document rather than at a homepage, and that eleven of them did not before
this pass. The one entry that names a finding instead of a work is flagged as
such, in the file and in the failing gate, rather than dressed up.
