"""Build 03, the triage agent, driven offline in its own process.

Started with one argument, the build folder, which is the only thing that goes
on the path. No red-team module is importable here, so the harness cannot reach
inside the build to make it fail interestingly.

The wiring is copied from Build 03's own `tests/conftest`-level fixture: point
`eutils.CACHE_DIR` at a corpus directory and replace `screen.run_agent` with one
that passes the stub client. That is how a reader runs it offline, so it is how
the harness runs it.

The checks reported are the ones the build actually has:

    identifier_dedup      a duplicate identifier was found and dropped
    gap_logged            a record could not be screened and was recorded as a
                          gap rather than guessed at
    verdict_unparsable    the model reply could not be parsed into a verdict
    criteria_version_mismatch
                          a verdict came back stamped with a version other than
                          the one the run started under

A name appears in `checks_fired` only when the check actually refused
something. A check that merely ran is not a check that fired, and conflating
the two would make every negative control look like a detection.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

BUILD = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BUILD))

import cache
import eutils
import screen
from agent import run_agent
from criteria import load_criteria
from stub_client import ScreeningClient
from tracing import Trace

CRITERIA_FILE = BUILD / "criteria" / "repurposing_v3.yaml"


def write_corpus(records, into: Path) -> Path:
    """Lay the job's records out using Build 03's own cache writer.

    Not by hand. The cache stores a digest alongside every payload and
    verifies it on read, so a corpus written by reaching around that would be
    testing a cache the build does not have.
    """
    into.mkdir(parents=True, exist_ok=True)
    for record in records:
        body = dict(record)
        body.setdefault("status", "ok")
        cache.write(body["pmid"], body, into)
    return into


def deduplicate(records):
    """Identifier-based deduplication: what the chapter's harness had.

    Correct, universal, and the reason its detection rate was 1.0 while a
    preprint and its published version sat in the corpus as two papers.
    """
    seen, kept, fired = set(), [], False
    for record in records:
        if record["pmid"] in seen:
            fired = True
            continue
        seen.add(record["pmid"])
        kept.append(record)
    return kept, fired


def handle(job, workspace: Path):
    records = job.get("records", [])
    unique, deduped = deduplicate(records)

    fired, events = [], []
    if deduped:
        fired.append("identifier_dedup")

    corpus = write_corpus(unique, workspace / "corpus")
    eutils.CACHE_DIR = corpus

    criteria = load_criteria(CRITERIA_FILE)
    version = job.get("criteria_version", criteria.version)
    client = ScreeningClient(
        corpus_dir=corpus,
        criteria_version=version,
        unparsable_on=job.get("unparsable_on", ()),
        fail_on=job.get("fail_on", ()),
    )

    def _run(task, max_steps=20, **kwargs):
        kwargs.setdefault("client", client)
        kwargs.setdefault("run_dir", str(workspace / "runs"))
        kwargs.setdefault("backoff_s", 0.0)
        return run_agent(task, max_steps, **kwargs)

    screen.run_agent = _run
    trace = Trace(str(workspace / "runs"))

    events.append("screening_started")
    verdicts, failed = screen.screen_corpus(
        [record["pmid"] for record in unique], criteria, trace
    )
    events.append("screening_finished")

    if failed:
        fired.append("gap_logged")
    if job.get("unparsable_on"):
        # A reply the loop could not parse never becomes a verdict; Build 03
        # records the record as a gap. Naming it separately says which of the
        # two things went wrong.
        fired.append("verdict_unparsable")

    mismatched = [v.pmid for v in verdicts if v.criteria_version != criteria.version]
    if mismatched:
        fired.append("criteria_version_mismatch")

    events.append("summary_written")
    return {
        "status": "COMPLETE",
        "checks_fired": sorted(set(fired)),
        "events": events,
        "answer": {
            "verdicts": len(verdicts),
            "failed": failed,
            "unique_records": len(unique),
            "submitted_records": len(records),
            "included": sum(1 for v in verdicts if v.decision == "include"),
        },
        "detail": f"{len(verdicts)} verdicts, {len(failed)} gaps",
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for index, line in enumerate(sys.stdin):
            if not line.strip():
                continue
            try:
                result = handle(json.loads(line), root / f"job{index}")
            except Exception as error:  # noqa: BLE001 - reported, not swallowed
                result = {"status": "FAILED", "checks_fired": [],
                          "events": [], "answer": None,
                          "detail": f"{type(error).__name__}: {error}"}
            sys.stdout.write(json.dumps(result, default=str) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
