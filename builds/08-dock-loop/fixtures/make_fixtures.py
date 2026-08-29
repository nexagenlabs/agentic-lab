"""Builds every fixture in this folder, deterministically.

The output is committed, so nothing needs running to use the build. This file
is here because a recorded docking output with fabricated coordinates is a
thing a reader should be able to inspect the construction of rather than
trust: the redocking RMSD and the cluster occupancy the gate asserts on are
computed from these coordinates, so a fixture that quietly made them easy
would make the whole control meaningless.

Run it from the build folder:

    python fixtures/make_fixtures.py

Everything here is invented. No PDB identifier, no coordinate, no score and no
compound in the output is real.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent

# A fabricated eight-atom ligand, as a rigid template. Real ligands have
# torsions and the poses would differ internally; these differ only by
# placement, which is enough for an RMSD and honest about being a fixture.
TEMPLATE = [
    (0.00, 0.00, 0.00), (1.42, 0.00, 0.00), (2.13, 1.23, 0.00),
    (1.42, 2.46, 0.00), (0.00, 2.46, 0.00), (-0.71, 1.23, 0.00),
    (-2.13, 1.23, 0.35), (3.55, 1.23, -0.35),
]
ELEMENTS = ["C", "C", "C", "C", "C", "N", "O", "O"]

BOX_CENTRE = (18.40, -4.25, 31.10)


def place(offset, rotation_deg=0.0):
    """Put the template somewhere, rigidly."""
    angle = math.radians(rotation_deg)
    cos, sin = math.cos(angle), math.sin(angle)
    out = []
    for x, y, z in TEMPLATE:
        rx = x * cos - y * sin
        ry = x * sin + y * cos
        out.append((rx + offset[0], ry + offset[1], z + offset[2]))
    return out


def pdbqt(poses_and_scores) -> str:
    """Write poses the way Vina writes them, MODEL block per pose."""
    lines = []
    for index, (coordinates, score) in enumerate(poses_and_scores, start=1):
        lines.append(f"MODEL {index}")
        lines.append(f"REMARK VINA RESULT:{score:>10.1f}{0.0:>11.3f}{0.0:>11.3f}")
        for serial, ((x, y, z), element) in enumerate(
                zip(coordinates, ELEMENTS, strict=True), start=1):
            lines.append(
                f"ATOM  {serial:>5} {element + str(serial):<4} LIG A   1    "
                f"{x:>8.3f}{y:>8.3f}{z:>8.3f}  1.00  0.00    "
                f"{0.0:>6.3f} {element:>2}"
            )
        lines.append("ENDMDL")
    return "\n".join(lines) + "\n"


def offset(dx, dy, dz):
    return (BOX_CENTRE[0] + dx, BOX_CENTRE[1] + dy, BOX_CENTRE[2] + dz)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def structures():
    """Six receptor records: two holo, one apo, three predicted."""
    records = [
        {"target": "KIN-ALPHA", "source": "EXPERIMENTAL",
         "identifier": "9XX1", "method": "X-ray",
         "resolution_angstrom": 1.85, "ligand_state": "holo",
         "cocrystal_ligand": "LIG-CRYSTAL", "prediction_confidence": None,
         "retrieved_at": "2026-02-11T09:00:00+00:00"},
        {"target": "KIN-BETA", "source": "EXPERIMENTAL",
         "identifier": "9XX2", "method": "X-ray",
         "resolution_angstrom": 2.10, "ligand_state": "holo",
         "cocrystal_ligand": "LIG-BETA-1", "prediction_confidence": None,
         "retrieved_at": "2026-02-11T09:04:00+00:00"},
        {"target": "KIN-GAMMA", "source": "EXPERIMENTAL",
         "identifier": "9XX3", "method": "cryo-EM",
         "resolution_angstrom": 3.40, "ligand_state": "apo",
         "cocrystal_ligand": None, "prediction_confidence": None,
         "retrieved_at": "2026-02-11T09:08:00+00:00"},
        {"target": "KIN-DELTA", "source": "PREDICTED",
         "identifier": "MOD-9XX4", "method": "AF3",
         "resolution_angstrom": None, "ligand_state": "unknown",
         "cocrystal_ligand": None, "prediction_confidence": 91.4,
         "retrieved_at": "2026-02-11T09:12:00+00:00"},
        {"target": "KIN-EPSILON", "source": "PREDICTED",
         "identifier": "MOD-9XX5", "method": "AF3",
         "resolution_angstrom": None, "ligand_state": "unknown",
         "cocrystal_ligand": None, "prediction_confidence": 62.8,
         "retrieved_at": "2026-02-11T09:16:00+00:00"},
        {"target": "KIN-ZETA", "source": "PREDICTED",
         "identifier": "MOD-9XX6", "method": "HelixFold3",
         "resolution_angstrom": None, "ligand_state": "predicted_holo",
         "cocrystal_ligand": "LIG-ZETA-1", "prediction_confidence": 84.2,
         "retrieved_at": "2026-02-11T09:20:00+00:00"},
    ]
    for record in records:
        write(HERE / "structures" / f"{record['target']}.json",
              json.dumps(record, indent=2) + "\n")
    return records


def redock():
    """One receptor with a known pose, and a docking that recovers it.

    The top pose is displaced from the crystal pose by a fixed amount in each
    coordinate, so the RMSD is exactly the length of that displacement. It is
    1.13 angstroms, which clears two and is not suspiciously close to zero.
    """
    crystal = place(offset(0.0, 0.0, 0.0))
    step = 1.13 / math.sqrt(3.0)
    recovered = [(x + step, y + step, z + step) for x, y, z in crystal]

    write(HERE / "redock" / "crystal_pose.json", json.dumps({
        "target": "KIN-ALPHA",
        "ligand_id": "LIG-CRYSTAL",
        "note": "Fabricated. The pose the ligand was stripped from.",
        "coordinates": [list(atom) for atom in crystal],
    }, indent=2) + "\n")

    # Second and third poses are elsewhere in the box, as a real run's are.
    poses = [
        (recovered, -9.6),
        (place(offset(3.4, -1.2, 0.9), 35.0), -8.8),
        (place(offset(-4.1, 2.6, -1.4), 110.0), -8.1),
        (place(offset(2.2, 1.1, -1.5), 18.0), -7.9),
    ]
    write(HERE / "vina_output" / "KIN-ALPHA__LIG-CRYSTAL.pdbqt", pdbqt(poses))


def cluster_and_outlier():
    """Two results with the same top score and different distributions.

    They are written to be indistinguishable on the number a ranking uses.
    Both top out at minus 9.4. The difference is that one has eight poses
    within two angstroms of the top pose and the other has one, and that is
    only visible if the whole distribution was kept.
    """
    tight = [(place(offset(0.0, 0.0, 0.0)), -9.4)]
    for index in range(1, 8):
        jitter = 0.18 * index
        tight.append((place(offset(jitter, -jitter * 0.4, jitter * 0.3),
                            2.0 * index), -9.4 + 0.05 * index))
    write(HERE / "vina_output" / "KIN-BETA__LIG-CLUSTER.pdbqt", pdbqt(tight))

    scattered = [(place(offset(0.0, 0.0, 0.0)), -9.4)]
    for index in range(1, 8):
        scattered.append((
            place(offset(5.5 + 1.4 * index, -3.2 - 1.1 * index,
                         2.1 + 0.8 * index), 40.0 * index),
            -7.6 + 0.06 * index,
        ))
    write(HERE / "vina_output" / "KIN-BETA__LIG-OUTLIER.pdbqt", pdbqt(scattered))


def decoy_library():
    """Eight actives and forty property-matched decoys, plus their output.

    The scores are drawn from two overlapping distributions, not two separated
    ones. Actives score better on average and several decoys beat several
    actives, which is what a real enrichment looks like. A library where every
    active outranks every decoy would make the control pass and prove nothing.
    """
    rng = random.Random(20260829)
    library = []
    for index in range(1, 9):
        library.append({"ligand_id": f"ACT-{index:03d}", "active": True,
                        "molecular_weight": round(rng.uniform(310, 430), 1),
                        "logp": round(rng.uniform(1.8, 3.9), 2)})
    for index in range(1, 41):
        library.append({"ligand_id": f"DEC-{index:03d}", "active": False,
                        "molecular_weight": round(rng.uniform(310, 430), 1),
                        "logp": round(rng.uniform(1.8, 3.9), 2)})

    scores = {}
    for entry in library:
        centre = -9.1 if entry["active"] else -7.9
        scores[entry["ligand_id"]] = round(rng.gauss(centre, 0.75), 1)

    write(HERE / "decoys" / "library.json", json.dumps({
        "note": ("Fabricated. Decoys are property matched on molecular weight "
                 "and logP only, which is weaker than a real decoy set and is "
                 "stated rather than implied."),
        "target": "KIN-BETA",
        "compounds": library,
    }, indent=2) + "\n")

    for entry in library:
        ligand = entry["ligand_id"]
        top = scores[ligand]
        poses = [
            (place(offset(0.0, 0.0, 0.0)), top),
            (place(offset(1.1, -0.6, 0.4), 20.0), round(top + 0.4, 1)),
            (place(offset(-2.8, 1.9, -1.1), 75.0), round(top + 0.9, 1)),
        ]
        write(HERE / "vina_output" / f"KIN-BETA__{ligand}.pdbqt", pdbqt(poses))
    return scores


def cross_target_results():
    """One ligand against four targets, for the provenance and box tests."""
    for target, top in (("KIN-ALPHA", -9.2), ("KIN-BETA", -8.7),
                        ("KIN-DELTA", -10.4), ("KIN-EPSILON", -11.9)):
        poses = [
            (place(offset(0.0, 0.0, 0.0)), top),
            (place(offset(0.7, -0.5, 0.3), 15.0), round(top + 0.3, 1)),
            (place(offset(-1.9, 1.2, -0.8), 60.0), round(top + 0.8, 1)),
        ]
        write(HERE / "vina_output" / f"{target}__LIG-PROBE.pdbqt", pdbqt(poses))


if __name__ == "__main__":
    structures()
    redock()
    cluster_and_outlier()
    scores = decoy_library()
    cross_target_results()
    print(f"wrote fixtures under {HERE}")
    print(f"library scores span {min(scores.values())} to {max(scores.values())}")
