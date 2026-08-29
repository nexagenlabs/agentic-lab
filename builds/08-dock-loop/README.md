# Build 08: Dock Loop

Introduced in **Chapter 7** of *The Agentic Lab*, "Target and Molecule Triage:
Structure Tools Inside an Agent Loop".

Structure retrieval with provenance, a declared grid box, a docking run,
result parsing, and a ranking that carries its own controls.

## A docking score is a ranking, not a measurement

Score to affinity correlations run from 0.10 to 0.38 across seven programs on
roughly 1,300 complexes, and one benchmark recorded AutoDock Vina at minus
0.18. Absolute predictions carry 1.5 to 2.0 log units of error, which is a
factor of thirty to a hundred on a Kd.

Enrichment is the claim docking supports: given a library, it puts more actives
near the top than chance would. So `affinity.py` exports `predicted_kd`,
`predicted_ki`, `predicted_binding_affinity` and `score_to_affinity`, and every
one of them raises with those numbers in the message. As with `accuracy` in
Build 04, refusing is stronger than omitting: a module with no affinity
function is an invitation to write one.

## This is the build where everything can work and the science still be wrong

So two of the seven tests are not tests of the code. They are controls the
campaign runs on itself.

**Redocking.** Take a receptor whose ligand pose is known, strip the ligand,
dock it back, and see whether the top pose lands within two angstroms of where
it actually sits. The fixture recovers it to 1.13 angstroms. If a setup cannot
recover an answer it already has, nothing it says about an unknown compound is
worth reading.

**Enrichment.** Dock eight known actives among forty property-matched decoys
and compute the enrichment factor. The fixture gives 3.6 at ten per cent
against a threshold of 2.0 that is passed in rather than defaulted, because
enrichment at one per cent and at ten per cent are different claims.

## Four things that are structural rather than remembered

**Ranking refuses a mixed set.** A result set holding both `EXPERIMENTAL` and
`PREDICTED` structures raises unless the caller passes
`allow_mixed_provenance=True`, and the flag is written to the manifest.
Docking to as-is predicted models performed consistently worse than to
experimental holo structures across twenty-two targets, with enrichment
factors of zero on several. A mixed set is defensible; a mixed set nobody
recorded as mixed is not.

**The box is a parameter, and a comparison set has one strategy.**
`build_comparison_set` refuses a set whose boxes were drawn different ways.
Chapter 7's failure account is four isoforms getting four boxes over four
days, each sensible on its own morning, producing numbers nobody could
compare. Nobody made a mistake. There was simply nothing that knew the four
runs were meant to be one comparison.

**Preparation decisions are declared.** Protonation state at assay pH,
crystallographic waters, metals and cofactors, ligand tautomer. Not one of
them has a default, and waters kept selectively have to be named. Undeclared
defaults are how two runs of the same nominal protocol diverge.

**The whole pose distribution is kept.** `cluster_occupancy` counts how many
poses sit within two angstroms of the best scoring one. The two fixtures in
`fixtures/vina_output/` that demonstrate this carry the same top score of
minus 9.4: one has eight poses in the cluster and the other has one. Nothing
that reduces a run to the number a ranking uses can tell them apart.

## The engine is a subprocess, and the tests do not need it

AutoDock Vina is a command-line program, and so is nearly every other
structure tool in this chapter, so `engine.py` treats it as one.

- `VinaEngine` shells out, passing the seed and the exhaustiveness explicitly.
  It is what a reader runs. It raises `engine_not_installed` rather than
  failing obscurely when the binary is absent.
- `RecordedEngine` replays output captured under `fixtures/vina_output/`. It
  is what the gate runs.

Both return the same bytes, so the parsing, the controls and the ranking sit
above the difference and cannot tell which one answered. **No test requires
Vina to be installed and none touches the network.** No docking library was
added to `requirements.txt`; the parsing is a regular expression and fixed
column offsets, which is what reading a PDBQT file actually takes.

## The manifest is the input, not the log

Everything the run needed is in `RunManifest`: engine, seed, exhaustiveness,
every box, the preparation decisions, the structure records, the pairs, and
the mixed-provenance flag. `rerun_from_manifest` takes the manifest and an
engine and nothing else.

The seed and the exhaustiveness are the two fields easiest to omit and worst
to omit. Search is stochastic, and a run at exhaustiveness 8 is not a repeat
of a run at 32. `SCORE_TOLERANCE` is 0.01 kcal/mol: with the recorded engine
two runs agree exactly, and the tolerance exists for the live case.

## Run it

```python
from campaign import run_campaign
from comparison import build_comparison_set
from engine import RecordedEngine        # or VinaEngine()
from models import PreparationDecisions

campaign = run_campaign(
    [("KIN-ALPHA", "LIG-PROBE"), ("KIN-BETA", "LIG-PROBE")],
    build_comparison_set("SET-KIN-01", boxes),
    records,
    preparation,
    RecordedEngine(recordings="fixtures/vina_output"),
    seed=20260829,
    exhaustiveness=16,
)
for entry in campaign.ranking:
    print(entry.position, entry.ligand_id, entry.score, entry.source)
```

There is no model call anywhere in this build, so there is no model name to
configure and no stub client to drive. The scepticism is arithmetic.

## Tests

```
pytest builds/08-dock-loop/tests/
```

Nineteen, none of which touches the network or requires Vina. The seven the
spec names are present under those names.

## What is not here

No structure retrieval over the network, which would be a live dependency the
gate cannot have. No ligand preparation, no minimisation, no free energy
calculation, and no attempt to say what a score means in kcal/mol, which is
the point of the build rather than an omission from it.

The RMSD is atom-order matched and not symmetry corrected, which is wrong for
a symmetric ligand. `geometry.py` says so where it is defined rather than
leaving a reader to discover it.
