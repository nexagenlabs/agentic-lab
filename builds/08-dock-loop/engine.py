"""The engine, behind an interface, because it is a subprocess.

AutoDock Vina is a command-line program. It is not a Python library and
pretending otherwise would teach the wrong pattern: nearly every real
structure tool in this chapter is an executable you hand a file to and read a
file back from, and the awkward parts, the seed, the exhaustiveness, the
missing binary, are properties of that shape.

Two implementations. ``VinaEngine`` is what a reader runs and it shells out.
``RecordedEngine`` replays output captured from a run that already happened,
and it is what the gate runs, so the tests never require Vina to be installed.
Both return the same bytes, so the parsing, the scoring and every control in
this build sit above the difference and cannot tell which one answered.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from models import DockingBox


class EngineError(RuntimeError):
    """The engine could not be run, or did not produce output."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class DockingEngine(Protocol):
    """What the rest of the build is allowed to know about an engine."""

    name: str

    def dock(self, target: str, ligand_id: str, box: DockingBox, *,
             seed: int, exhaustiveness: int) -> str:
        """Return the raw output file the engine wrote."""


@dataclass
class VinaEngine:
    """The real one. Never invoked by a test."""

    binary: str = "vina"
    receptor_dir: Path = Path("receptors")
    ligand_dir: Path = Path("ligands")
    out_dir: Path = Path("runs/poses")
    name: str = "autodock-vina"

    def dock(self, target: str, ligand_id: str, box: DockingBox, *,
             seed: int, exhaustiveness: int) -> str:
        if shutil.which(self.binary) is None:
            raise EngineError(
                "engine_not_installed",
                f"{self.binary} is not on PATH. Install AutoDock Vina, or run "
                "with RecordedEngine, which is what the tests do.",
            )
        self.out_dir.mkdir(parents=True, exist_ok=True)
        out_path = self.out_dir / f"{target}__{ligand_id}.pdbqt"
        centre_x, centre_y, centre_z = box.centre_xyz
        size_x, size_y, size_z = box.size_xyz

        # The seed and the exhaustiveness are passed explicitly and recorded
        # in the manifest. Search is stochastic, and a run you cannot replay
        # is a run Chapter 9 cannot replay either.
        command = [
            self.binary,
            "--receptor", str(self.receptor_dir / f"{target}.pdbqt"),
            "--ligand", str(self.ligand_dir / f"{ligand_id}.pdbqt"),
            "--center_x", str(centre_x),
            "--center_y", str(centre_y),
            "--center_z", str(centre_z),
            "--size_x", str(size_x),
            "--size_y", str(size_y),
            "--size_z", str(size_z),
            "--seed", str(seed),
            "--exhaustiveness", str(exhaustiveness),
            "--out", str(out_path),
        ]
        # check=False on purpose: a non-zero exit becomes a structured
        # EngineError below, not a CalledProcessError nobody catches.
        finished = subprocess.run(command, capture_output=True,
                                  text=True, check=False)
        if finished.returncode != 0:
            raise EngineError(
                "engine_failed",
                f"{self.binary} exited {finished.returncode}: "
                f"{finished.stderr.strip()[:400]}",
            )
        if not out_path.exists():
            raise EngineError(
                "no_output", f"{self.binary} wrote nothing to {out_path}"
            )
        return out_path.read_text(encoding="utf-8")


@dataclass
class RecordedEngine:
    """Replays captured output. Deterministic, and offline by construction."""

    recordings: Path
    name: str = "autodock-vina (recorded)"
    calls: list[dict[str, object]] = field(default_factory=list)

    def dock(self, target: str, ligand_id: str, box: DockingBox, *,
             seed: int, exhaustiveness: int) -> str:
        self.calls.append({
            "target": target, "ligand_id": ligand_id, "seed": seed,
            "exhaustiveness": exhaustiveness,
            "comparison_set_id": box.comparison_set_id,
        })
        path = Path(self.recordings) / f"{target}__{ligand_id}.pdbqt"
        if not path.exists():
            raise EngineError(
                "no_recording",
                f"no recorded output for {target} against {ligand_id}. Record "
                "one rather than letting a test reach for a real engine.",
            )
        return path.read_text(encoding="utf-8")
