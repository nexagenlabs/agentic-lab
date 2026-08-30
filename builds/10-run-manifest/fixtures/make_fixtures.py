"""Builds every fixture in this folder, deterministically and twice the same.

The output is committed, so nothing needs running to use the build. This file
is here because the four recorded runs are the evidence the gate reasons over,
and a reader should be able to inspect how they were constructed rather than
take them on trust. In particular the drifted run has to be a *fair* version of
the chapter's failure account: four external responses revised, the code and
the model untouched, and six fewer inclusions arriving as a consequence rather
than as something typed in. The numbers this file prints when it runs are the
numbers the gate asserts on, and they are computed here rather than chosen.

Run it from the build folder:

    python fixtures/make_fixtures.py

Everything here is invented. No record, no endpoint, no digest and no commit
hash corresponds to anything real.

Determinism matters more here than in most fixture generators. Every digest in
every manifest is a hash of bytes this file wrote, so a wall clock anywhere in
the run would produce a different trace on every invocation and the committed
fixtures would stop matching their own generator. The clock is injected and the
serialisation is canonical, which is the same discipline the build asks of the
pipeline it replays.
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from hashing import hash_file, hash_json, write_json
from models import (
    ExternalCall,
    InputRecord,
    ManifestBuilder,
    ModelUse,
    OutputRecord,
)
from pipeline import ENRICHMENT_ENDPOINT, batches, enrichment_query, screen
from stub_client import StubModel
from tracing import Trace

# Fabricated, and fixed so that two runs of this file agree byte for byte.
BASE_TIME = datetime(2026, 2, 17, 9, 0, 0, tzinfo=timezone.utc)
COMMIT = "4f1c9ae37b62d0518c4a7e9f2b3d6084ac15e7d9"
PYTHON_VERSION = "3.11.9"
MODEL_ID = "stub-screener"
MODEL_VERSION = "2026-05-01"

CORPUS_SIZE = 36
EARLIEST_YEAR = 2015

LOCKFILE = """# Fabricated lock file, for a fabricated run.
anthropic==0.42.0
pydantic==2.9.2
pyyaml==6.0.2
"""


class FixedClock:
    """One second per event, so the trace is a function of its contents."""

    def __init__(self, start: datetime) -> None:
        self._at = start

    def __call__(self) -> str:
        stamp = self._at.isoformat()
        self._at += timedelta(seconds=1)
        return stamp


def corpus() -> list[dict[str, Any]]:
    """Thirty-six fabricated records, spread either side of the year window."""
    return [
        {
            "id": f"REC-{index:03d}",
            "title": f"Fabricated study {index} of a fabricated compound",
            "abstract": (
                f"Record {index}. Written for a fixture and reporting nothing. "
                "Any resemblance to a real study is accidental."
            ),
            "year": 2012 + (index % 14),
        }
        for index in range(1, CORPUS_SIZE + 1)
    ]


def criteria() -> dict[str, Any]:
    return {
        "version": 3,
        "question": (
            "Does the record report a numerical endpoint in a qualifying "
            "model published in or after 2015?"
        ),
        "earliest_year": EARLIEST_YEAR,
        "include_if_all": ["numeric_endpoint", "year_in_window"],
        "on_ambiguity": "flag",
    }


def base_facts() -> dict[str, dict[str, Any]]:
    """What the enrichment database said on the day of the first run."""
    facts = {}
    for index in range(1, CORPUS_SIZE + 1):
        facts[f"REC-{index:03d}"] = {
            "has_numeric_endpoint": index % 3 != 0,
            "ambiguous": index % 11 == 0,
            "retracted": False,
        }
    return facts


class Enrichment:
    """The database, as a callable over a fixed table."""

    def __init__(self, table: dict[str, dict[str, Any]]) -> None:
        self.table = table

    def __call__(self, batch: list[str]) -> dict[str, Any]:
        return {record_id: self.table[record_id] for record_id in batch}


def write_inputs(root: Path) -> list[InputRecord]:
    """The three input files, hashed as they are written."""
    write_json(root / "inputs/corpus.json", corpus())
    write_json(root / "inputs/criteria.json", criteria())
    (root / "inputs/requirements.lock.txt").write_text(
        LOCKFILE, encoding="utf-8", newline="\n"
    )
    records = []
    for relative in ("inputs/corpus.json", "inputs/criteria.json",
                     "inputs/requirements.lock.txt"):
        path = root / relative
        records.append(InputRecord(
            path=relative,
            sha256=hash_file(path),
            bytes=path.stat().st_size,
            retrieved_at=BASE_TIME,
        ))
    return records


def build_run(root: Path, run_id: str, facts: dict[str, dict[str, Any]],
              status: str = "COMPLETE", halt_reason: str | None = None,
              git_dirty: bool = False,
              truncate_after: int | None = None) -> dict[str, Any]:
    """Record one complete run: inputs, trace, outputs, manifest.

    ``truncate_after`` produces the incomplete fixture by stopping the run
    partway, which is how an incomplete run actually happens. Writing an
    INCOMPLETE status onto a finished run would make the fixture agree with
    the test and disagree with reality.
    """
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)

    inputs = write_inputs(root)
    lockfile_sha = next(record.sha256 for record in inputs
                        if record.path.endswith("requirements.lock.txt"))

    trace = Trace(run_dir=str(root), run_id=run_id, clock=FixedClock(BASE_TIME))
    client = StubModel(MODEL_ID, MODEL_VERSION)

    records = corpus()
    if truncate_after is not None:
        records = records[:truncate_after]

    result = screen(records, criteria(), client, Enrichment(facts), trace)
    trace.write("run_finished", status=status, halt_reason=halt_reason,
                steps=len(records))

    outputs = []
    for relative, text in sorted(result["outputs"].items()):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")
        outputs.append(OutputRecord(path=relative, sha256=hash_file(path),
                                    bytes=path.stat().st_size))

    builder = ManifestBuilder(
        run_id=run_id,
        started_at=BASE_TIME,
        python_version=PYTHON_VERSION,
        lockfile_sha256=lockfile_sha,
        git_commit=COMMIT,
        git_dirty=git_dirty,
        models=[ModelUse(id=MODEL_ID, version=MODEL_VERSION, temperature=0.0,
                         seed=20260217)],
        inputs=inputs,
        external_calls=[
            ExternalCall(endpoint=call["endpoint"], query=call["query"],
                         response_sha256=call["response_sha256"],
                         called_at=BASE_TIME)
            for call in result["external_calls"]
        ],
        criteria_version=criteria()["version"],
        mapping_ids=["MAP-INSTR-07"],
        design_ids=["TMZ-NA-U87-001"],
        approvals=["PROP-9f3a21c40b by S. Bramall"],
        outputs=outputs,
    )
    manifest = builder.finish(
        status=status,
        finished_at=BASE_TIME + timedelta(minutes=4),
        trace_path=f"{run_id}.jsonl",
        trace_sha256=hash_file(root / f"{run_id}.jsonl"),
        halt_reason=halt_reason,
    )
    write_json(root / "manifest.json", manifest.model_dump(mode="json"))

    summary = json.loads((root / "outputs/summary.json").read_text("utf-8"))
    return {"manifest": manifest, "summary": summary,
            "calls": result["external_calls"]}


def drifted_facts(facts: dict[str, dict[str, Any]],
                  included: list[str]) -> tuple[dict[str, Any], list[str]]:
    """Revise upstream records so that six inclusions stop qualifying.

    The six are chosen to land in exactly four of the six enrichment batches,
    because the chapter's account is four responses moving. They are picked by
    walking the included records in order rather than by being listed, so the
    fixture cannot quietly stop being what it claims when the corpus changes.
    """
    order = sorted(facts)
    batch_of = {record_id: index
                for index, batch in enumerate(batches(order))
                for record_id in batch}

    revised = {record_id: dict(fact) for record_id, fact in facts.items()}
    by_batch: dict[int, list[str]] = {}
    for record_id in included:
        by_batch.setdefault(batch_of[record_id], []).append(record_id)

    # Two from each of the first two usable batches and one from each of the
    # next two: six records, four responses. Taken in order rather than listed,
    # so the fixture cannot drift away from what it claims to be.
    usable = [index for index in sorted(by_batch) if len(by_batch[index]) >= 2]
    chosen = (by_batch[usable[0]][:2] + by_batch[usable[1]][:2]
              + by_batch[usable[2]][:1] + by_batch[usable[3]][:1])
    touched = {batch_of[record_id] for record_id in chosen}
    if len(touched) != 4 or len(chosen) != 6:
        raise RuntimeError(
            f"the drift is meant to touch four batches and six records, and "
            f"it touched {len(touched)} and {len(chosen)}"
        )
    for record_id in chosen:
        revised[record_id]["retracted"] = True
    return revised, chosen


def changed_calls(before: list[dict[str, Any]],
                  after: list[dict[str, Any]]) -> list[str]:
    was = {call["query"]: call["response_sha256"] for call in before}
    return sorted(call["query"] for call in after
                  if was.get(call["query"]) != call["response_sha256"])


def main() -> None:
    facts = base_facts()
    stored = build_run(HERE / "stored_run", "run-2026-02-17-a", facts)

    verdicts = json.loads(
        (HERE / "stored_run/outputs/verdicts.json").read_text("utf-8")
    )
    included = [verdict["id"] for verdict in verdicts
                if verdict["decision"] == "include"]

    revised, chosen = drifted_facts(facts, included)
    drifted = build_run(HERE / "drifted_run", "run-2026-08-11-b", revised)

    build_run(HERE / "dirty_run", "run-2026-02-18-c", facts, git_dirty=True)

    build_run(
        HERE / "incomplete_run", "run-2026-02-19-d", facts,
        status="INCOMPLETE",
        halt_reason="step cap of 20 reached with 16 records unscreened",
        truncate_after=20,
    )

    moved = changed_calls(stored["calls"], drifted["calls"])
    before, after = stored["summary"]["included"], drifted["summary"]["included"]
    print(f"wrote four runs under {HERE}")
    print(f"  stored:   {before} included of {stored['summary']['corpus_size']}")
    print(f"  drifted:  {after} included, {before - after} fewer")
    print(f"  revised upstream records: {', '.join(chosen)}")
    print(f"  external responses changed: {len(moved)} of "
          f"{len(stored['calls'])}")
    print(f"  corpus snapshot {stored['manifest'].corpus_snapshot_id[:16]} "
          f"to {drifted['manifest'].corpus_snapshot_id[:16]}")
    print(f"  same commit in both: {stored['manifest'].git_commit == drifted['manifest'].git_commit}")
    print(f"  enrichment endpoint: {ENRICHMENT_ENDPOINT}")
    print(f"  first query: {enrichment_query(sorted(facts)[:6])}")
    print(f"  a response digest: {hash_json({'example': True})[:16]}")


if __name__ == "__main__":
    main()
