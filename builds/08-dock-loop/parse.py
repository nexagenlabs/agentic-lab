"""Reading what the engine actually wrote.

Real docking engines are command-line tools that leave a file behind, so the
parsing is the interface, not a Python API. Vina writes one MODEL block per
pose with its score on a REMARK line, in the order it ranked them, and every
pose it found is in there. Keeping all of them is the point: the top score is
what a ranking uses, and the rest is the only evidence about whether that top
score means anything.
"""

from __future__ import annotations

import re

from models import Pose

SCORE_RE = re.compile(r"REMARK\s+VINA\s+RESULT:\s*(-?\d+\.\d+)")


class ParseError(RuntimeError):
    """The engine output cannot be read."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _coordinates(block: str) -> list[tuple[float, float, float]]:
    out = []
    for line in block.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        # Fixed columns, as in the PDB format Vina writes. Splitting on
        # whitespace works until an atom name runs into a residue number.
        out.append((float(line[30:38]), float(line[38:46]), float(line[46:54])))
    return out


def parse_poses(text: str) -> list[Pose]:
    """Every pose in the output file, in the order the engine ranked them."""
    blocks = [block for block in text.split("MODEL")[1:] if "ENDMDL" in block]
    if not blocks:
        raise ParseError(
            "no_models",
            "the output holds no MODEL blocks, so the run produced no poses",
        )

    poses = []
    for index, block in enumerate(blocks, start=1):
        found = SCORE_RE.search(block)
        if found is None:
            raise ParseError(
                "no_score",
                f"pose {index} carries no REMARK VINA RESULT line, so it has "
                "a geometry and no score",
            )
        coordinates = _coordinates(block)
        if not coordinates:
            raise ParseError("no_atoms", f"pose {index} carries no atoms")
        poses.append(Pose(rank=index, score=float(found.group(1)),
                          coordinates=coordinates))
    return poses
