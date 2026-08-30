# Fixtures for Build 12

## Almost nothing here is new

The desk reuses the earlier builds' fixtures rather than inventing its own, and
reads them as files rather than importing any of their modules:

| What | From |
|---|---|
| The corpus, 61 records | `builds/03-triage-agent/fixtures/corpus/` |
| Criteria version 3 | `builds/03-triage-agent/criteria/repurposing_v3.yaml` |
| The gold labels behind the known answer | `builds/03-triage-agent/fixtures/gold.json` |
| The structure record for KIN-BETA | `builds/08-dock-loop/fixtures/structures/` |
| Recorded docking output | `builds/08-dock-loop/fixtures/vina_output/` |
| The design protocol adaptation starts from | `builds/06-plate-mapper/designs/` |

Everything in those folders is fabricated, and each of them says so in its own
README. No PMID, DOI, journal, docking score, cell line or compound
measurement anywhere in this repository is real.

Three things are new here.

## `question.yaml`

The question the chapter asks: which approved antiparasitic agents show
evidence of activity against PKC isoforms in liver-derived human cell models.

**Read this before reading the shortlist.** Build 03's corpus is a
hepatotoxicity corpus. It contains amiodarone, paracetamol, silibinin,
clozapine and a dozen other approved drugs assayed for liver toxicity. It
contains ivermectin exactly once, in a record about OATP1B1 transport in HEK293
cells, which screening excludes correctly because HEK293 is not a liver model.

So the question and the corpus do not match, and the desk answers the question
the corpus can support. That mismatch is not a defect in this fixture and it
has not been papered over. It is the most useful thing the assembled desk
demonstrates, and the build README says why at length: every component gate
passes, every stage does its job, and the end-to-end answer is to a different
question from the one that was asked.

`compound_ligands` maps a compound name to a ligand identifier a docking run
can address. In a real desk that comes from a chemical registry; here it is a
declared input with a hash in the manifest. The assignment is alphabetical,
and alphabetical matters: the ranking is by docking score, so a mapping chosen
after looking at the scores would be a shortlist chosen by hand. The rule was
fixed before any score was read.

## `checkpoints/`

Three recorded approvals, so the gate runs unattended. Written by
`make_checkpoints.py`, which is committed alongside them.

The generator exists because an approval is bound to a hash of what was
approved, so the committed approvals have to be regenerated whenever a stage
changes what it produces. Doing that by hand would mean pasting digests, which
nobody would check. Run it from the build folder:

```
python fixtures/make_checkpoints.py
```

The approver name and all three notes are fabricated. The note on the shortlist
approval records the reviewer saying the shortlist does not answer the question
that was asked, which is the judgement a real reviewer should have made at that
checkpoint, and the fact that it is fabricated is the second finding in the
build README: a checkpoint is only as good as the person at it.

## `known_answer/shortlist.json`

Produced by hand. `make_checkpoints.py` does not touch it, and neither does any
other code in this build.

That separation is the point. A known answer produced by the system it checks
is a tautology, and `test_shortlist_matches_known_answer` would then be
asserting that the desk agrees with itself. The file records how it was
derived, in five steps, so a reader can redo it: start from Build 03's
committed gold labels rather than from this desk's screening, read the
compounds out of the included abstracts, map them by the alphabetical rule the
question declares, read the best score from Build 08's recorded output, sort
and take three.

It also records what agreement would and would not prove, which is worth as
much as the shortlist. It matched. That establishes that the desk's screening
agrees with Build 03's hand labels on the records that decide the top three and
that the mapping, parsing and ranking arithmetic are right. It establishes
nothing about whether these compounds are worth anybody's time, because the
corpus, the labels, the scores and this file all came out of the same project.
