# Build 06: Plate Mapper

Introduced in Chapter 6 of *The Agentic Lab*, "Protocol Agents: Drafting,
Adapting and Sanity-Checking Wet-Lab Procedures".

## What this build does

It lays out a combination matrix, checks the dilution arithmetic before
anything is pipetted, and forces a commitment to a synergy model before any
data exists.

There is **no model call anywhere in this build**. Every check is arithmetic
and every input is a file. The agent's job in this chapter is to propose a
layout and record a claim; the checking is Python, and Python is the only
thing that touches a number.

## The timestamp is the point

Chapter 6 opens with an admission: the matrices were run, and the synergy
model was chosen after the surfaces were seen. Four candidate models plus a
post-hoc choice is four chances at a positive number.

`check_commitment_precedes_data` compares `analysis.committed_at` against the
earliest reading in the results directory and fails if the model was chosen
once data existed.

Some readers will find that excessive. The reason is in the docstring and it
is worth repeating here: **a model chosen after the fact leaves no trace
anywhere a reader can find it.** Not in the analysis, which runs the chosen
model and reports it. Not in the figures, which show the model that was run.
Not in the methods section, which describes what was done and not when it was
decided. Every artefact of the study is consistent with the model having been
chosen first. The timestamp is the only surviving evidence, which is why it is
checked rather than trusted.

Timestamps are compared as instants, not wall clocks. The printed design
carries an India Standard Time offset, and comparing naively would be wrong by
five and a half hours, which is easily enough to flip the answer.

## Two refusals

`choose_synergy_model()` raises. It does not warn, default, or pick the most
common option. Bliss assumes the two agents act independently and multiply;
Loewe assumes a shared dose-equivalence relationship; HSA claims only that the
combination beats the better single agent; ZIP interpolates between Bliss and
Loewe. Those are different statements about biology and only one of them is
yours to make. The error message says all of that, so the refusal is useful
rather than merely obstructive.

`check_consensus` rejects any set containing **both Bliss and ZIP**. ZIP is
constructed by interpolating between the Bliss and Loewe reference models, so
a ZIP score already contains the Bliss claim and a consensus across both
double-counts one assumption. SynergyFinder excludes ZIP from its consensus
for exactly this reason. This is the trap most readers will not know.

## The RRID is not optional

The design carries `rrid: CVCL_0022`, not just `U87MG`. A commercial
authentication service found 4.7 per cent of submitted lines misidentified in
2024 and 2.4 per cent in 2025. A name is a label and labels have been wrong.
`validate_design` rejects a design that names a line without an identifier,
and rejects an identifier that is not in Cellosaurus form.

## The layout is reproducible or it is nothing

Controls sit on **every plate**, not on a reference plate, because plate
effects are real and a control measured on Tuesday cannot normalise a
treatment measured on Thursday.

Treatment positions are randomised within each plate from the seed recorded in
the design, so Build 05's wrangler can regenerate this exact map and verify
returning data against it. A layout you cannot reproduce is a layout nothing
can check.

## The printed design needs four plates

Worth knowing before you run it. The design asks for a 6 by 10 dose matrix,
which is 60 combinations, plus 12 control wells. Excluding the perimeter of a
96-well plate leaves 60 usable wells. Sixty combinations plus twelve controls
is 72, so **one replicate does not fit on one plate**, and the design asks for
three.

The layout therefore spans four plates: 48 treatment wells on each of the
first three, 36 on the fourth, with 12 wells left over and recorded as
`unused` rather than left blank. An unassigned well nobody wrote down is a
well somebody later assumes held something.

This is recorded in `HANDOFF.md` as a finding about the printed design rather
than worked around silently.

## The seven bad designs

In `fixtures/bad_designs/`, each failing exactly one validation, each with a
`.expected.json` naming the failure: `no_rrid`, `solvent_above_tolerance`,
`transfer_below_minimum`, `no_lower_plateau`, `wells_do_not_balance`,
`no_synergy_model`, `commitment_after_data`.

Most carry bench parameters in their `.expected.json` and a note saying why.
The printed design trips the solvent check at a 100 mM stock, so a design
testing a later check is reviewed against a 1 M stock; otherwise the solvent
failure fires first and masks the one under test.

## Run it

```
pytest builds/06-plate-mapper/tests/
```

No API key, no network, and no stub client either, because there is no model
call to stub.

To review a design of your own, from inside `builds/06-plate-mapper/`:

```python
from review import review_design

report = review_design("designs/tmz_na_u87mg.yaml",
                       results_dir="fixtures/results",
                       stock_mM=1000.0)
print(report["plates"], report["commitment"]["verdict"])
```

`review_design` raises `ReviewFailed` on the first refusal, carrying which
check refused it.

## What is not here

Protocol adaptation is Build 07, whose listing sits in the manifest set to
`skip` and whose target is `builds/07-protocol-adapter/models.py`. It has not
been started.
