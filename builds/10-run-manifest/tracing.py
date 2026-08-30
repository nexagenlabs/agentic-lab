"""Append-only JSONL for one run, and the reader that replays it.

Copied from Build 02 rather than imported. Each build stands alone, so what
this one needs it carries.

One addition, and it is the addition the whole build rests on: the trace
records **what the model actually said**, not only what was concluded from it.
``model_completion`` events carry the raw completion text verbatim.

That distinction is the difference between the two kinds of replay. A trace of
conclusions lets you check that somebody's summary matched their notes. A trace
of completions lets you rebuild the outputs from the model's own words with no
model present, which is what still works after the vendor has deprecated the
version you ran. It costs more disk. Disk is the cheapest thing in the
building, and a deprecated model is not purchasable at any price.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class Trace:
    """One JSON object per line, written as the run happens.

    A run you cannot replay is a run you cannot debug, and appending a line is
    the only write that survives a process being killed halfway through.
    """

    def __init__(self, run_dir: str = "runs", run_id: str | None = None,
                 clock: Any = None) -> None:
        self.run_id = run_id or uuid.uuid4().hex[:12]
        # Injected so a fixture generator can produce a byte-identical trace
        # twice. A wall clock in a fixture is a fixture that never reproduces.
        self._clock = clock or (lambda: datetime.now(timezone.utc).isoformat())
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        self.path = Path(run_dir) / f"{self.run_id}.jsonl"

    def write(self, event: str, **fields: Any) -> None:
        record = {"run_id": self.run_id, "ts": self._clock(),
                  "event": event, **fields}
        with self.path.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, default=str, sort_keys=True) + "\n")

    def events(self) -> list[dict[str, Any]]:
        return read_trace(self.path)


def read_trace(path: str | Path) -> list[dict[str, Any]]:
    """Every event, in the order it was written."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def completions(events: list[dict[str, Any]]) -> list[str]:
    """The raw text the model returned, in order, and nothing else.

    Audit replay reads this and only this from the model side. If it ever
    starts reading a field this build wrote as a conclusion, the replay has
    stopped proving that the result followed from the inputs and started
    proving that a summary was copied correctly.
    """
    return [event["text"] for event in events
            if event["event"] == "model_completion"]


def external_responses(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event for event in events if event["event"] == "external_call"]
