"""Stage 4: the trace. One JSON object per line, written as the run happens.

JSONL from the first version, because a run you cannot replay is a run you
cannot debug, and because appending a line is the only write that survives a
process being killed halfway through.
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from anthropic import Anthropic
from config import MODEL
from stage2 import SEARCH_PUBMED
from stage3 import dispatch


class Trace:
    """Append-only JSONL for one run."""

    def __init__(self, run_dir: str = "runs") -> None:
        self.run_id = uuid4().hex[:12]
        self.path = Path(run_dir) / f"{self.run_id}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, event: str, **fields: Any) -> None:
        record: dict[str, Any] = {
            "run_id": self.run_id,
            "ts": datetime.now(UTC).isoformat(),
            "event": event,
        }
        record.update(fields)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")


def run_agent(task: str, max_steps: int = 20) -> dict[str, Any]:
    client = Anthropic()
    trace = Trace()
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    steps = 0
    trace.write("run_start", task=task, model=MODEL, max_steps=max_steps)
    while steps < max_steps:
        steps += 1
        trace.write("model_call", step=steps, model=MODEL)
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=[SEARCH_PUBMED],
            messages=messages,
        )
        trace.write("model_response", step=steps, model=response.model,
                    stop_reason=response.stop_reason)
        if response.stop_reason != "tool_use":
            answer = "".join(b.text for b in response.content if b.type == "text")
            trace.write("halt", reason="complete", steps=steps, max_steps=max_steps)
            return {"status": "COMPLETE", "steps": steps, "answer": answer,
                    "run_id": trace.run_id}
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            trace.write("tool_request", step=steps, tool=block.name, args=block.input)
            result = dispatch(block.name, block.input)
            trace.write("tool_result", step=steps, tool=block.name,
                        status=result["status"], code=result.get("code"))
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": results})
    trace.write("halt", reason="step_cap", steps=steps, max_steps=max_steps)
    return {"status": "INCOMPLETE", "reason": "step_cap", "steps": steps,
            "answer": None, "run_id": trace.run_id}


if __name__ == "__main__":
    print(run_agent("What has been published on olaparib in ovarian carcinoma?"))
