"""Append-only JSONL for one run.

Copied from Build 02 rather than imported. Each build stands alone, so what
this one needs it carries.
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

    def __init__(self, run_dir: str = "runs") -> None:
        self.run_id = uuid.uuid4().hex[:12]
        Path(run_dir).mkdir(parents=True, exist_ok=True)
        self.path = Path(run_dir) / f"{self.run_id}.jsonl"

    def write(self, event: str, **fields: Any) -> None:
        record = {"run_id": self.run_id,
                  "ts": datetime.now(timezone.utc).isoformat(),
                  "event": event, **fields}
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")

    def events(self) -> list[dict[str, Any]]:
        """Read the trace back, for a test or a difference report."""
        if not self.path.exists():
            return []
        with self.path.open(encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]
