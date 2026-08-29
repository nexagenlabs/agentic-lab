# SPEC: Build 08, dock-loop

**Chapter 7, "Target and Molecule Triage: Structure Tools Inside an Agent
Loop".**

## Purpose

Structure retrieval with provenance, a declared grid box, a docking run, result
parsing, and a ranking that carries its own controls.

This is the build where the agent can be working perfectly and the science
still be worthless, so it has the most sceptical gate in the book. Two of its
four named tests are controls run inside the campaign rather than checks on the
code.

The chapter's argument, which the build must embody: **a docking score is a
ranking, not a measurement.** Score to affinity correlations run from 0.10 to
0.38 across seven programs on roughly 1,300 complexes, and one benchmark
recorded AutoDock Vina at minus 0.18. Enrichment is the claim docking supports.
Nothing in this build may present a score as an affinity.

## Files and printed listings

| Listing | File |
|---|---|
| `01_structure_record` | `models.py` |
| `02_docking_box` | `models.py` |

Both `mode: exact`, both in the same file, so they must appear as two separate
verbatim blocks.

## The docking engine

AutoDock Vina, invoked as a subprocess. **The tests must not require it to be
installed.** Wrap it behind an interface with a real implementation and a
fixture-backed stub that replays recorded output. The stub is what the gate
runs; the real one is what a reader runs.

Add to `requirements.txt` only what you need for parsing. Do not add a Python
docking library; the point is the subprocess pattern, since real engines are
command-line tools.

## Behaviour required

**Provenance is structural.** `StructureRecord` as printed. Two fields carry
the weight: `ligand_state` records the apo and holo distinction that dominates
screening performance, and `prediction_confidence` is specified over the pocket
rather than the whole chain, because a model with excellent global confidence
and a poorly resolved binding site is exactly the case that misleads you.

**Ranking refuses a mixed set.** A result set containing both `EXPERIMENTAL`
and `PREDICTED` entries raises unless the caller passes an explicit flag, and
the flag is written to the manifest. This is Chapter 2's failure fixed
structurally, now with numbers behind it: docking to as-is AlphaFold models
performed consistently worse than to experimental holo structures across
twenty-two targets, with enrichment factors of zero on several.

**The box is a parameter.** `DockingBox` as printed, and the
`comparison_set_id` guard is the smallest piece of code in the chapter with the
largest effect: within a comparison set every target must share one strategy.
Construction of a set with mixed strategies raises. This is the chapter's
failure account, where four isoforms got four boxes over four days and the
numbers were incomparable.

**Preparation decisions are declared, not defaulted.** Protonation state at
assay pH, retention of crystallographic waters, handling of metals and
cofactors, ligand tautomer. Each is a field with no default. Undeclared
defaults are how two runs of the same nominal protocol diverge.

**Keep the whole pose distribution.** Not just the top pose. A top score from a
single outlier pose is different evidence from one supported by a tight
cluster, and the cluster is only visible if you retain the distribution.

**Record the seed and exhaustiveness.** Search is stochastic. A run you cannot
reproduce is a run Chapter 9 cannot replay.

**Consensus is supported and honestly limited.** Rank aggregation across
several scoring functions is available. The docstring must say plainly that
consensus reduces the variance of a ranking and does not turn it into an
affinity.

**No affinity claim anywhere.** Any method returning a predicted Kd, Ki or
binding affinity must raise, with a message citing the correlation range and
the 1.5 to 2.0 log unit error on absolute predictions. As with `accuracy` in
Build 04, refusing is stronger than omitting.

## Fixtures

- `fixtures/structures/`, six fabricated receptor records: two experimental
  holo with co-crystallised ligands, one experimental apo, two predicted with
  differing pocket confidence, one predicted holo.
- `fixtures/vina_output/`, recorded engine output for the stub to replay,
  including one multi-pose result with a tight cluster and one whose top score
  rests on a single outlier.
- `fixtures/redock/`, one receptor with a known co-crystallised ligand pose, for
  the redocking control.
- `fixtures/decoys/`, forty property-matched decoys and eight known actives, so
  enrichment is computable.

Fabricate everything. No real PDB identifiers, no real coordinates.

## Gate: `pytest builds/08-dock-loop/tests/`

**`test_redocking_control_recovers_pose`**
Strip the ligand from the redock fixture, dock it back, assert the top pose
falls within two angstroms of the crystallographic pose. If the setup cannot
recover a known answer, nothing it says about an unknown compound is worth
reading.

**`test_decoy_enrichment_exceeds_threshold`**
Dock the decoy set alongside the actives, compute an enrichment factor, assert
it clears a threshold passed in rather than defaulted.

**`test_ranking_rejects_mixed_provenance`**
Assert a set containing one experimental and one predicted structure raises,
and succeeds only with the explicit flag, and that the flag reaches the
manifest.

**`test_comparison_set_enforces_one_box_strategy`**
Assert constructing a comparison set from two different box strategies raises.

**`test_run_is_reproducible_from_manifest`**
Re-run from the manifest alone; assert scores match within documented
tolerance.

**`test_affinity_prediction_is_refused`**
Assert any affinity method raises with a message explaining why.

**`test_pose_distribution_is_retained`**
Assert the outlier fixture and the cluster fixture are distinguishable from the
stored output.

No test may require Vina to be installed, and none may touch the network.

## Report back

Against the five points in `CLAUDE.md`, plus: the redocking RMSD your fixture
produces, the enrichment factor, and whether the outlier and cluster fixtures
are distinguishable on score alone or only on the distribution. If they are
distinguishable on score alone, the fixtures are too easy and should be
rebuilt.
