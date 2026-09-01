# Reference resolution

Companion to `references_report.md`, which is machine-generated. This file
records what a human decision still hangs on. Produced by running
`tools/verify_references.py` against `references/references.yaml` until the
output was byte-identical between consecutive runs.

Four passes. The first checked the list as it stood. The second found the list
was the wrong list. The third closed it against the printed page. The fourth
split the prose and built the checker that keeps the two records honest.

---

## Pass 4 — the note/gloss split and the checker

### First: the refreshed appendix did not land

`references/APPENDIX_D_AS_PRINTED.md` on disk is **byte-identical to the
version committed in c783b82**. `git diff` is empty for it, its mtime predates
the last commit's other files, and none of the three new identifiers appear in
it: no `10.1007/BF01952257`, no `10.1002/9781119536604`, no `ALTEX`. Rows 20,
28 and 34 still read exactly as they did.

Nothing here is blocked by that — everything below is built and delivered — but
the new checker is red on two rows because of it, and it will go green the
moment the file is saved. I verified that rather than assuming it: applying
your three described fixes to a scratch copy takes the checker from 2
disagreements to **0**, and the scratch copy was then discarded.

```
--- against a copy with your three fixes applied
0 printed rows disagree with the verified record.        exit=0

--- against the file as it actually is on disk
row 20 (cochrane_handbook_v6): year 2019 not on the page
row 28 (loewe1926combination): title not on the page: "Über Kombinationswirkungen"
2 printed rows disagree with the verified record.        exit=1
```

Row 34 already passes, because it is a description row and exempt — see below.

### 1. The note/gloss split

`references.yaml` now carries two prose fields, documented in its header:

- **`gloss:`** reader-facing. This is what prints in Appendix D after the
  bibliographic record, and it is the only prose in the file a reader ever
  sees.
- **`note:`** maintenance. How the entry was resolved, what was checked, what
  is still open. **Never prints.**

13 entries carry a gloss; 45 carry a note. Two long notes were split, their
reader-facing halves lifted out verbatim: the Biomni preprint-title warning
(printed entry 1) and the Szymanski NOVEL-to-INORGANIC explanation (printed
entry 7), which now ends in `gloss` where it belongs — "the word that left the
title is the word the correction was about."

Ten glosses existed **only on the printed page** and had no counterpart in the
file at all. They are now transcribed in: "Engineering documentation" on
entries 12, 14 and 70; "Statistical data validation for dataframes" on 26;
"Commercial authentication service report" on 35; "Specifically section
11.10(e) on audit trails" on 42; "Indirect prompt injection evaluation" on 47;
and the three further-reading glosses on 71 to 73. Before this pass, anyone
regenerating appendix text from `references.yaml` would have dropped all ten
without noticing.

A test guards the direction of the split. `test_gloss_never_carries_maintenance_prose`
bars a set of maintenance phrases — "appendix d reads", "not mine to make",
"only the abstract", "unsourced", "crossref returns" — from the field that
prints. Getting the two backwards is the failure mode, and it is silent.

### 2. The checker

`tools/appendix_render.py`, wrapped by
`tests/test_printed_rows_match_record.py`. It renders only the bibliographic
half of each entry — authors, title, venue, volume, pages, year, DOI, arXiv id
— and asserts each field appears in the matching printed row. Prose, ordering
and grouping stay with you.

```
python tools/appendix_render.py          check every printed row
python tools/appendix_render.py --emit   strings for rows still printed
                                         as a description
```

**Comparison is on words alone** — lowercased, accents stripped, punctuation
collapsed. The page and the record disagree about punctuation constantly and
harmlessly: "Archiv fur" against "Archiv für", an en dash for a hyphen, a
middle dot in 2·5. A check that failed on those would be switched off within a
week. Page ranges are matched in both forms, because the house style prints
"716 to 723" where the record stores `716-723`.

**Two escape hatches, both explicit, both per row, both counted.**

- `printed_as: description` — 19 rows still print a description of a finding
  rather than a citation. They carry no title or author to compare. This is the
  set `--emit` exists to empty.
- `omits: [year]` — 5 rows where the printed style deliberately carries no such
  field: no arXiv id on entry 4, no date on the Pandera or further-reading
  rows, no pages on the Chang working paper, no year on 21 CFR Part 11.
  **Omission is an editorial choice; contradiction is the error.** Naming the
  field per row keeps the choice visible instead of relaxing the check for
  everybody. `title`, `authors` and `doi` cannot be omitted — they are what the
  check exists to protect, and a test asserts `omits` never names anything else.

Both counts are asserted, so neither can quietly grow. If a citation regressed
into a description the description count would rise, and that is a bug rather
than a number to edit.

### Proving it bites

You asked for a year and a title. Both were run against a copy of the appendix
with your three fixes applied, so the mutation is the only cause of failure.
Both were reverted; `git diff` on the appendix is clean and the yaml carries no
residue.

**Baseline** — `0 printed rows disagree with the verified record.` exit 0

**Mutation 1, a year.** `swanson2025virtuallab`, `year: 2025` → `2024`:

```
row 2 (swanson2025virtuallab):
    year 2024 not on the page
1 printed rows disagree with the verified record.        exit=1
```

**Mutation 2, a title.** `landis1977kappa`, "categorical" → "categorial" — a
one-letter change of the kind that survives every check the repository had
before today:

```
row 17 (landis1977kappa):
    title not on the page: "The measurement of observer agreement for categorial data"
1 printed rows disagree with the verified record.        exit=1
```

The second is the important one. That mutation passes the Crossref verifier
(the DOI still resolves, and 97 similarity clears the threshold), passes the
manifest test (same id, same chapter, phrase still anchored), and would have
printed. Only holding the two records against each other catches it — which is
the whole argument for not generating one from the other.

### Corrections made this pass

1. **Two titles adopted from the printed page**, which carries the fuller
   official form of each and is the only authority for both, since neither is
   Crossref-checkable. `cfr21part11` becomes "US Code of Federal Regulations,
   Title 21, Part 11: Electronic records; electronic signatures"; `eu_ai_act`
   gains "of the European Parliament and of the Council".
2. **Authors added to two entries that had none**, both from an authoritative
   source rather than recall: `mas_vs_sas_2025` from the arXiv listing (Gao,
   Li, Liu, Yu, Wang, Lin and Lai) and `clinical_scale_orchestration_2025` from
   Crossref (Klang, Omar, Raut et al.). Both are rows you are about to paste, so
   they should not go in headless.
3. **Two renderer bugs**, found by reading its own output: a title ending in a
   question mark produced "screening?." and a proceedings paper with pages but
   no volume ran the page range into the conference name.
4. `entry 34` still has **no authors** — Crossref returns none against
   `10.14573/altex.2507041`, and I have not filled them in from elsewhere.

### Two things worth printing that are not printed

Neither is an error, so neither is a checker failure. Both are declared in
`omits` and both would improve the page.

- **Entry 4 gives no locator at all.** "BixBench … FutureHouse and Bioml
  (2025)" has no arXiv id, no DOI, no URL. The record has `arXiv:2503.00096`. A
  reader cannot find it from what is printed.
- **Entry 26 dates nothing.** "Pandera documentation" names no version and no
  access date, and documentation is versioned rather than dated. The record
  carries an access year of 2026, and `REVIEW.md` pins pandera 0.33.0 while the
  stable docs banner reads 0.32.0. A documentation citation naming no version
  cannot be checked by anybody later.

### Counts, unchanged from pass 3

| Status | Count |
| --- | --- |
| CONFIRMED | 42 |
| MISMATCH | 0 |
| UNRESOLVED | 0 |
| UNSOURCED | **1** |
| SKIPPED | 30 |
| total | **73** |

Entry 68, `practitioner2026_coordination`, stays UNSOURCED by your decision.
`--emit` deliberately refuses to render it: producing a citation-shaped string
for an unsourced entry is precisely the artefact this whole exercise exists to
keep out of the book.

Full suite: **140 passed, 1 failed.** The failure is the checker on rows 20 and
28, from the un-saved appendix file. Report stable across consecutive runs.

---

## Strings for the description rows

Eighteen rows, every one rendered from the verified record. Your list named 13;
these are the five you did not name and that I also resolved: **34, 54, 59, 67,
69**. Entry 68 is absent on purpose.

The full text is in the terminal output of:

```
python tools/appendix_render.py --emit
```

Re-run it rather than copying from this file — that is one fewer transcription
between the verified record and the page, and a lost digit is exactly what you
were avoiding. Once a row is pasted in, drop its `printed_as: description` line
from `references/appendix_d.manifest.yaml` and lower `EXPECTED_DESCRIPTIONS` in
`tests/test_printed_rows_match_record.py`. The checker then starts enforcing
that row field by field, permanently.

---

## Pass 3 — diffed against Appendix D as printed

`references/APPENDIX_D_AS_PRINTED.md` arrived with all 74 printed rows, so the
five-row shortfall could be resolved instead of estimated.

### The five

They are not five missing citations. Three are, and two are structural.

| Printed | What it is | Outcome |
| --- | --- | --- |
| **21** | "Comparative evaluation of large language models for title and abstract screening against a low-prevalence gold standard set (2026)" | New work, **resolved** with a DOI |
| **22** | "Evaluation of large language model agreement with human screeners across six systematic reviews in software engineering (2026)" | New work, **resolved** to an arXiv preprint |
| **27** | "Silent failure and data consistency decay in multi-agent pipelines (2026)" | New work, **resolved** to an arXiv preprint |
| **74** | "Anthropic engineering blog and the Model Context Protocol documentation, both of which are updated more often than any book can be." | Not a new work — a further-reading pointer to two living sources, both already cited elsewhere in the list. It had no counterpart here because it is a sentence, not a citation |
| **63** | "US Food and Drug Administration and European Medicines Agency. Guiding principles of good artificial intelligence practice in drug development (January 2026)" | Not a new work — **the same document as printed entry 8**, repeated under Chapter 11 |

So **74 printed rows describe 73 distinct works**, and `references.yaml` now
holds 73 entries. The arithmetic closes exactly.

**No sixth or seventh turned up.** Every one of the 69 entries mapped onto a
printed row, and every printed row mapped onto an entry. Nothing in
`references.yaml` was absent from the appendix, which was the other way this
could have gone.

On the repeat at 8 and 63: the manifest records it with `duplicate_of` rather
than collapsing it. The printed page genuinely has 74 numbered rows, and a
manifest holding 73 would disagree with anyone counting the book. Whether the
appendix *should* print it twice is an editorial question — a reference list
that carries one document under two numbers is doing something a reader will
notice — but that is yours, and the machinery now describes what is there
rather than what would be tidier.

### Counts

| Status | Pass 1 | Pass 2 | Pass 3 |
| --- | --- | --- | --- |
| CONFIRMED | 24 | 40 | **42** |
| MISMATCH | 0 | 0 | 0 |
| UNRESOLVED | 0 | 0 | 0 |
| UNSOURCED | 1 | 2 | **1** |
| SKIPPED | 22 | 27 | **30** |
| **total** | 47 | 69 | **73** |

Manifest test: **7 passed**, including the count assertion that failed last
pass. Full suite: **136 passed, 0 failed.** Report stable across consecutive
runs.

### DOIs added

| Entry | DOI | Work |
| --- | --- | --- |
| `nawrath2026screening` | `10.3390/info17050501` | Nawrath et al., *Validating Large Language Models for Title-Abstract Screening in Low-Prevalence Systematic Reviews*, Information 17:501 |
| `yu2026af3bias` | `10.1073/pnas.2530709123` | Yu et al., *Bias in the AlphaFold3 prediction of ligand-induced domain motion in enzymes*, PNAS 123 |
| `chang2015replicable` | `10.17016/FEDS.2015.083` | Chang & Li, FEDS 2015 — **replaces** the 2022 DOI entered last pass, see below |

Two more resolved to real works with no Crossref DOI, verified by arXiv ID:

- `mantyla2026disagreements` — arXiv 2606.17588, submitted 16 June 2026
- `liu2026silentfailure` — arXiv 2606.08162, submitted 6 June 2026

### The AlphaFold 3 entry is no longer unsourced

This is the pass's best result and it came free with the printed page. The
hand-written list I worked from last pass said "Evaluation of AlphaFold 3 for
protein-ligand prediction (2025 to 2026)". The printed appendix says
"…for protein-ligand complex prediction **and its conformational biases**
(2025 to 2026)".

Those three words are the discriminator. Without them the description matched
four different 2025–2026 evaluations and I marked it UNSOURCED rather than
guess. With them it matches one: Yu, Bekar-Cesaretli, Lazou, Kozakov,
Joseph-McCarthy and Vajda, PNAS, 4 March 2026, `10.1073/pnas.2530709123`.

What it found, for the sentence in Chapter 7: ensembles of AlphaFold3 models
for 82 enzymes, generated with and without ligand. Where the PDB holds more apo
than holo structures, 64.8 % of ligand-free models sit closer to the open apo
state. Where it holds more holo than apo, **75.5 % of models generated with no
ligand at all adopt the holo conformation.** That is memorisation of
training-set composition rather than physics, and adding the ligand only
moderately shifts it except for proteins with few structures. Confirm the
figure the chapter quotes is one of these two.

### How the ambiguous ones were pinned

Two of the three needed a candidate ruled out rather than a match asserted.

**#22** could have been either of two 2026 software-engineering screening
papers. *Beyond Accuracy: LLM Variability in Evidence Screening for Software
Engineering SLRs* (arXiv 2604.27006) has "software engineering" in its title,
which is the tempting match — but it covers **two** reviews and benchmarks
against classical classifiers, not humans. *Understanding LLMs in
Title-Abstract Screening* (arXiv 2606.17588) covers **six** software
engineering systematic reviews, over 1,000 primary studies, human experts
against LLMs zero-shot, Cohen's kappa 0.52 to 0.77. The appendix says six, and
says human screeners. Ruled in on the numbers, not the title.

Worth noticing for Chapter 4: 0.52–0.77 straddles the moderate/substantial
boundary in the Landis and Koch bands the book already cites at
`landis1977kappa`, and screening is exactly the class-imbalanced setting
`byrt1993pabak` and `gwet2008ac1` are in the list to warn about. Those belong
in one sentence.

**#27** looked unresolvable at first. arXiv 2606.08162's *abstract* neither
names "data consistency decay" nor mentions data pipelines, and I nearly marked
it unsourced on that basis. The full text settles it: "Data Consistency Decay
(L3 — Execution)" is a named row in its failure taxonomy, described as gradual
divergence between recorded and actual state in agent-managed data pipelines
where every step runs correctly and the aggregate is systematically wrong, and
it tabulates consistency falling from 100 % at one hop to **23.5 % at ten**.
Both halves of the appendix's description are the paper's own terms.

Cite it for the failure mode it names, not for the law it proposes: it is a
single-author preprint offering an entropy model, S(t) = S₀e^(αt), as a
principle, on 40,000 trials nothing independent has reproduced.

### Corrections made to references.yaml from the printed page

1. **Chang & Li: the appendix answers the question I raised.** Last pass I
   flagged two versions with different subtitles and entered the published 2022
   *Critical Finance Review* article. The printed appendix cites the **2015
   Federal Reserve working paper** — "usually not", Finance and Economics
   Discussion Series — fully and coherently specified. The entry now follows
   the printed page: `chang2015replicable`, `10.17016/FEDS.2015.083`. Both DOIs
   resolve, so upgrading to the 2022 version later is a real option; do it in
   both files at once, and note the replication counts are reported differently
   between them.
2. **The Mars Climate Orbiter report belongs to Chapter 5, not Chapter 10.** I
   filed it under Chapter 10 on the reasoning that unit errors are a Chapter 10
   topic. The appendix files it under Data-Wrangling Agents. The chapter
   assertion in the manifest test caught it.
3. Volume and pages added to `bhattacharyya2023fabricated` (Cureus 15, e39238),
   taken from the printed row.
4. Author diacritics restored where an earlier pass had flattened them —
   Łaźniewski, López-Muñoz, Hornbæk, Németh.

### Errors in the printed appendix

Beyond 67 and 69, which you already named.

1. **Entry 28 prints a title that does not exist.** "Effects of combinations:
   mathematical basis of the problem" is an English rendering with a subtitle
   attached. Crossref holds the paper as "Über Kombinationswirkungen"; the
   subtitle corresponds to the first communication's subhead, "I. Mitteilung:
   Hilfsmittel der Fragestellung". **A reader searching the printed title finds
   nothing.** Print the German title, or the German with a bracketed
   translation.
2. **Entry 34's year is wrong.** The appendix says 2026; Crossref dates the
   GIVReSt guidance to ALTEX volume 42, **2025**. The entry also still bundles
   three documents into one row.
3. **Entry 20 pairs a 2024 date with a 2019 book.** The appendix says "version
   6. Cochrane (2024)", which is the continuously-revised online handbook at
   `training.cochrane.org/handbook`. The DOI that resolves,
   `10.1002/9781119536604`, is the Wiley printed edition of September 2019.
   Different artefacts. Pick one — and if it is the online handbook, it needs a
   point release and an access date, because "version 6" alone will not
   identify what was read.
4. **Entry 59 is weaker than I said last pass, but still worth fixing.** As
   printed, "more than two million published papers" is *true* — the audit
   covered 2.47 million. My earlier note called it an understatement of the
   source, and that was too strong. The remaining objection is real though: the
   paper titles itself "an audit across 2·5 million biomedical papers", so a
   reader following the citation meets a different number from the one the book
   gave them, and the book chose the least impressive true statement available.
   Say 2.5 million.
5. **Entry 54's "and simulation studies" is fine.** I flagged it as possibly
   unsupported, because the RSOS abstract does not mention simulation studies.
   The body does: advice on saving raw per-dataset results of long runs, and on
   not letting results depend on core count or parallelisation backend. The
   entry stands as printed. Retracting my concern.

### Still unsourced

One, unchanged since pass 1.

**`practitioner2026_coordination`** — printed entry 68, "Orchestration overhead
and coordination cost in production agent pipelines. Practitioner measurements
(2026)", supporting the Chapter 12 orchestration-overhead passage. Nothing
sources it. You already removed the 950 ms-against-500 and
29,000-tokens-against-10,000 figures and labelled the eighty per cent claim as
one team's report. I have not gone looking for something close enough to
attach, in three passes now, because a plausible near-match is the failure and
not the fix.

---

## Generating Appendix D from references.yaml

You asked for a proposal, not a build. Here is the proposal, and it is a
qualified no — generate the mechanical half, not the whole thing.

### What stands in the way right now

**`note:` is two fields wearing one name.** Some notes are prose that belongs in
the printed book: the Szymanski title explanation, ending "the word that left
the title is the word the correction was about", is written for a reader and
prints today as entry 7. Others are verification working notes that must never
print: "THE ENTRY IS STALE AND THE FIX IS NOT MINE TO MAKE", "Appendix D reads
…", "Crossref returns type edited-book", "only the abstract was read here". A
generator that printed `note` would put my scaffolding into your book.

**Some printed prose exists nowhere else.** Entry 42's "Specifically section
11.10(e) on audit trails", entry 47's "Indirect prompt injection evaluation",
and the further-reading glosses at 71 to 73 ("The origin of the table shape
Chapter 5 targets") are on the printed page and not in `references.yaml`. A
generator would silently drop them.

**Claim order is not in `references.yaml` and is not derivable.** It is the
order a chapter makes its arguments in. It exists today only as the printed
numbering, which the manifest now carries as `n`.

### What it would cost

| Step | Effort | Notes |
| --- | --- | --- |
| Split `note` into `note` (internal) and `gloss` (printed) | Half a day | 73 entries, ~45 with notes. A judgement call each; getting one wrong prints working notes into the book |
| Transcribe the ~10 printed glosses that exist only on the page | 30 min | Mechanical once located |
| Ordering: drive from the manifest's `n` | Free | The data already exists |
| Renderer: group by chapter, sort by `n`, format per house style | Half a day to a day | The fiddly part. Books, regulations, preprints and documentation each print differently, and the style spells ranges as "716 to 723" rather than an en dash |
| Round-trip test: render, diff against `APPENDIX_D_AS_PRINTED.md`, fail on any difference | 2 hours | This is the piece that makes it worth doing, and it forces the four above to actually be complete |

Call it **one focused day**, most of it in the `note`/`gloss` split rather than
in code.

### What it would lose

**The two witnesses collapse into one.** This is the real cost and it is not
small. The manifest test works today because `references.yaml` and the manifest
are two independently-maintained records of the same list, neither derived from
the other. Generate the appendix from the yaml and the appendix stops being
evidence: the test becomes a function checked against its own input. Single
source of truth is the right answer for *divergence*, which is what bit you.
It is the wrong answer for *wrongness*. If `references.yaml` carries a bad
title today, the printed page disagrees and someone can notice. Generated, the
book agrees with the error, confidently, and nothing in the system dissents.

Note that both failures found in this project were divergence in one direction
and staleness in the other — 47 against 74, then entries 67 and 69 frozen while
the yaml moved on. A generator kills both. But it also kills the mechanism that
*found* them.

**Editorial arrangement.** Entry 74 — "both of which are updated more often
than any book can be" — is a sentence about the appendix as an object, working
because it sits last. Renderers flatten that kind of thing first.

**The deliberate repeat.** Entries 8 and 63 have to be told to a generator;
they are not derivable from one `chapter:` field. Cheap to support, but a naive
one-entry-one-row renderer drops the repeat and takes the count from 74 to 73,
which looks like a fix and is not.

### What I would do instead

**Build a checker, not a generator**, and do the `note`/`gloss` split
regardless.

1. **Split `note` into `note` and `gloss` now.** Do this whether or not
   anything is ever generated. The file currently mixes shipping prose with
   working notes, and that is a live hazard the moment anyone copies from it —
   which is how appendix text gets written. Highest-value item on this page and
   independent of everything else.
2. **Render only the bibliographic half** of each entry — authors, title,
   venue, volume, pages, year, DOI — and assert it appears in the corresponding
   printed row of `APPENDIX_D_AS_PRINTED.md`. Leave prose, ordering and
   grouping to you and the page.

That buys the actual protection. A printed row could no longer disagree with
the verified record about a title, a volume, a year or a DOI, which is exactly
how 67 and 69 went stale and how entry 28 came to print a title that does not
exist. It costs about a third of the generator, and it keeps the property that
made this whole exercise work: two records, separately maintained, that have to
agree.

If you later want full generation, the checker is the right first step anyway.
It forces the formatting rules to be written down and proven against the real
page before anything depends on them — and at that point the generator is
mostly already written.

---

## Pass 2 — reconciling against Appendix D

> Superseded in places by pass 3, which had the printed page. Where the two
> disagree, pass 3 is right. In particular: the AlphaFold 3 entry is no longer
> unsourced, the Chang & Li version question is settled in favour of the 2015
> working paper, and the Lancet objection is weaker than stated here.

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

**`alphafold3_ligand_eval` — RESOLVED IN PASS 3**, once the printed wording
supplied the words "and its conformational biases". Left below as written,
because the reason it could not be closed from the hand-written list is the
point.

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
