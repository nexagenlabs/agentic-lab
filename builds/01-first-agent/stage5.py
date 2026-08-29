"""Stage 5: the remaining limits. Budget, error policy, write gate.

The circuit breaker arrives with the error policy, because a tool that has
failed three times running is not a transient problem, and retrying it is how
a run spends its whole budget on one broken thing.
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from anthropic import Anthropic, APIConnectionError, APIError
from config import MODEL
from stage2 import SEARCH_PUBMED, search_pubmed
from stage3 import check_search_pubmed
from stage4 import Trace

SAVE_NOTE = {
    "name": "save_note",
    "description": (
        "Append a note to the laboratory notebook. Use this when the user has "
        "asked for a finding to be recorded. Do NOT use this to keep working "
        "notes for yourself: the notebook is a record other people read."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The note, one paragraph."},
            "approved_by": {
                "type": "string",
                "description": "The person who approved this write.",
            },
        },
        "required": ["text", "approved_by"],
    },
}

TOOLS = [SEARCH_PUBMED, SAVE_NOTE]
WRITE_TOOLS = {"save_note"}

# Status codes that mean "the same request may work in a moment". Everything
# else, a 400 above all, means the request itself is wrong and always will be.
TRANSIENT_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})

FAILURE_LIMIT = 3


def save_note(text: str, approved_by: str, path: str = "notes.jsonl") -> dict[str, Any]:
    """Append one note to the notebook.

    ``approved_by`` is required: an unattributed write is not a record.
    """
    record = {
        "text": text,
        "approved_by": approved_by,
        "ts": datetime.now(UTC).isoformat(),
    }
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")
    return {"status": "ok", "written": path, "approved_by": approved_by}


def check_save_note(args: dict[str, Any]) -> str | None:
    text = args.get("text")
    if not isinstance(text, str) or not text.strip():
        return "text must be a non-empty string"
    approved_by = args.get("approved_by")
    if not isinstance(approved_by, str) or not approved_by.strip():
        return "approved_by is required"
    return None


CHECKS = {"search_pubmed": check_search_pubmed, "save_note": check_save_note}
FUNCTIONS = {"search_pubmed": search_pubmed, "save_note": save_note}


def is_transient(error: APIError) -> bool:
    """A dropped connection never reached a server, so it has no status code
    to read. Everything else is judged on the code it came back with."""
    if isinstance(error, APIConnectionError):
        return True
    return getattr(error, "status_code", None) in TRANSIENT_STATUS


def dispatch(
    name: str,
    args: dict[str, Any],
    trace: Trace,
    *,
    approved: bool = False,
) -> dict[str, Any]:
    """The gate every tool call passes: known tool, then write policy, then
    arguments. Nothing raises out of here."""
    if name not in FUNCTIONS:
        trace.write("tool_rejected", tool=name, code="unknown_tool")
        return {"status": "error", "code": "unknown_tool", "tool": name}
    if name in WRITE_TOOLS and not approved:
        trace.write("tool_blocked", tool=name, code="awaiting_human_approval")
        return {"status": "blocked", "code": "awaiting_human_approval", "tool": name}
    reason = CHECKS[name](args)
    if reason is not None:
        trace.write("tool_rejected", tool=name, code="invalid_arguments",
                    detail=reason, args=args)
        return {"status": "error", "code": "invalid_arguments", "detail": reason}
    return FUNCTIONS[name](**args)


def run_agent(
    task: str,
    max_steps: int = 20,
    *,
    client: Any = None,
    token_budget: int = 100_000,
    run_dir: str = "runs",
    backoff_s: float = 2.0,
) -> dict[str, Any]:
    client = client or Anthropic()
    trace = Trace(run_dir)
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    steps = 0
    tokens_used = 0
    retries = 0
    failures: dict[str, int] = {}
    disabled: set[str] = set()
    trace.write("run_start", task=task, model=MODEL, max_steps=max_steps,
                token_budget=token_budget)
    while steps < max_steps:
        # Before the call, not after: a budget checked afterwards is one that
        # has already been spent.
        if tokens_used >= token_budget:
            trace.write("halt", reason="budget", steps=steps,
                        max_steps=max_steps, tokens_used=tokens_used)
            return {"status": "INCOMPLETE", "reason": "budget", "steps": steps,
                    "answer": None, "run_id": trace.run_id}
        steps += 1
        tools = [tool for tool in TOOLS if tool["name"] not in disabled]
        trace.write("model_call", step=steps, model=MODEL)
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                tools=tools,
                messages=messages,
            )
        except APIError as error:
            status_code = getattr(error, "status_code", None)
            # The retry takes a step of its own, so a nested loop cannot hide
            # from the ceiling.
            if is_transient(error) and retries == 0:
                retries += 1
                trace.write("model_error", step=steps,
                            status_code=status_code, retrying=True)
                time.sleep(backoff_s)
                continue
            trace.write("model_error", step=steps,
                        status_code=status_code, retrying=False)
            trace.write("halt", reason="api_error", steps=steps, max_steps=max_steps)
            return {"status": "FAILED", "code": "api_error", "steps": steps,
                    "status_code": status_code, "answer": None,
                    "run_id": trace.run_id}
        retries = 0
        tokens_used += response.usage.input_tokens + response.usage.output_tokens
        trace.write("model_response", step=steps, model=response.model,
                    stop_reason=response.stop_reason, tokens_used=tokens_used)
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
            if block.name in disabled:
                result = {"status": "error", "code": "tool_disabled", "tool": block.name}
            else:
                result = dispatch(block.name, block.input, trace)
                if result["status"] == "error":
                    failures[block.name] = failures.get(block.name, 0) + 1
                    if failures[block.name] >= FAILURE_LIMIT:
                        disabled.add(block.name)
                        trace.write("circuit_open", tool=block.name,
                                    failures=failures[block.name])
                else:
                    failures[block.name] = 0
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
