# Fixture corpus for Build 08

## Everything here is fabricated

**No PDB identifier, no coordinate, no docking score and no compound in this
folder is real.** The six receptors are invented, their identifiers `9XX1` to
`9XX6` and `MOD-9XX4` to `MOD-9XX6` are not issued codes, the ligand is an
eight-atom template that is not a molecule anyone has made, and every number
in `vina_output/` was written by `make_fixtures.py` rather than measured.

This warning matters more here than in most of the builds. A folder of
plausible-looking docking output with plausible-looking scores is exactly the
material somebody quotes as a benchmark, and these scores benchmark nothing.
The correlations that make a docking score a ranking rather than a measurement
are in the chapter, and they are about real programs on real complexes; the
numbers here are set dressing for the machinery.

## The output is generated, and the generator is committed

`make_fixtures.py` writes everything else in this folder. Run it from the
build directory:

```
python fixtures/make_fixtures.py
```

It is committed because the two controls in the gate compute their numbers
from these coordinates rather than reading them from a file beside them. A
fixture that quietly made the redock easy, or made every active outscore every
decoy, would turn both controls into decoration. You should be able to see how
they were made and disagree with it.

## What each part is for

### `structures/`

Six records, and the spread is the point: two experimental holo structures
with named co-crystallised ligands, one experimental apo structure at poor
resolution, two predicted models with very different pocket confidence, 91.4
against 62.8, and one predicted holo. `ligand_state` and
`prediction_confidence` are the two fields that carry the weight, and the
records exist so that both can be exercised.

### `vina_output/`

Recorded engine output, one file per target and ligand pair, in the format
Vina writes: one `MODEL` block per pose with a `REMARK VINA RESULT` score and
the atoms underneath.

Two of them matter more than the rest. `KIN-BETA__LIG-CLUSTER.pdbqt` and
`KIN-BETA__LIG-OUTLIER.pdbqt` carry **the same top score**, minus 9.4, on
purpose. Eight poses sit within two angstroms of the cluster fixture's top
pose and one sits within two angstroms of the outlier's. Nothing that reduces
a run to the number a ranking uses can tell them apart. That is the whole
argument for keeping the pose distribution, and if the two were separable on
score alone the fixture would be proving something easier than it claims.

### `redock/`

`crystal_pose.json` holds the pose the ligand was stripped from.
`vina_output/KIN-ALPHA__LIG-CRYSTAL.pdbqt` is the docking that put it back.
The top pose sits 1.13 angstroms from the crystallographic one, which clears
the two angstrom convention without being suspiciously close to zero.

### `decoys/`

Eight actives and forty decoys with their recorded output. The scores are
drawn from two overlapping distributions rather than two separated ones, so
several decoys beat several actives and the best scoring compound in the whole
library is a decoy. The enrichment factor at ten per cent comes out at 3.6,
which is a real screen's kind of number rather than a demonstration's.

The decoys are property matched on molecular weight and logP only. A real
decoy set matches on more than that, and the shortfall is stated here rather
than implied by the word "matched".
