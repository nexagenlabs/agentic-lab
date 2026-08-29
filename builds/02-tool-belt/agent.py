"""The loop, unchanged from Build 01. Only the boundary underneath it changed.

Build 01 argued for the step cap, the budget checked before the call, the
one retry on a transient failure and the circuit breaker. None of that is
revisited here: this build is about what happens to a tool call once the
model has asked for one.
"""

import json
import time
from typing import Any

from anthropic import Anthropic, APIConnectionError, APIError
from config import MODEL
from dispatch import TOOLS, dispatch
from tracing import Trace

MAX_STEPS = 20

# The ceiling a run may spend. Checked before a call, never after.
TOKEN_BUDGET = 100_000

# What the next call is assumed to cost when deciding whether to make it.
ESTIMATED_CALL_TOKENS = 1_500

# Three consecutive failures from one tool is not bad luck, it is a broken
# tool. Disable it rather than spend the rest of the run rediscovering that.
FAILURE_LIMIT = 3

# Status codes that mean the same request may work in a moment. Everything
# else, a 400 above all, means the request itself is wrong and always will be.
TRANSIENT_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})

# Neither tool in this build writes anything, so the gate has nothing to stop.
# It stays because the next build adds a tool that does.
WRITE_TOOLS: set[str] = set()

# Approval arrives out of band, from a human, never from the arguments the
# model supplied: a model asked whether its own write was approved says yes.
APPROVALS: set[str] = set()


def approved(name: str, args: dict) -> bool:
    """Whether a human has approved this write."""
    return name in APPROVALS


def is_transient(error: APIError) -> bool:
    """A dropped connection never reached a server, so it has no status code
    to read. Everything else is judged on the code it came back with."""
    if isinstance(error, APIConnectionError):
        return True
    return getattr(error, "status_code", None) in TRANSIENT_STATUS


def run_agent(
    task: str,
    max_steps: int = MAX_STEPS,
    *,
    client: Any = None,
    token_budget: int = TOKEN_BUDGET,
    run_dir: str = "runs",
    backoff_s: float = 2.0,
) -> dict:
    client = client or Anthropic()
    trace = Trace(run_dir)
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    steps = 0
    tokens_used = 0
    estimated_next = ESTIMATED_CALL_TOKENS
    retries = 0
    failures: dict[str, int] = {}
    disabled: set[str] = set()
    trace.write("run_start", task=task, model=MODEL, max_steps=max_steps,
                token_budget=token_budget)

    while steps < max_steps:
        # Before the call, not after: a budget checked afterwards is one that
        # has already been spent.
        if tokens_used + estimated_next > token_budget:
            trace.write("halt", reason="budget", steps=steps,
                        max_steps=max_steps, tokens_used=tokens_used)
            return {"status": "INCOMPLETE", "reason": "budget", "steps": steps,
                    "answer": None, "run_id": trace.run_id}

        steps += 1
        tools = [tool for tool in TOOLS if tool["name"] not in disabled]
        trace.write("model_call", step=steps, model=MODEL)
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=2048, tools=tools, messages=messages,
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
        spent = response.usage.input_tokens + response.usage.output_tokens
        tokens_used += spent
        # The turn just measured is the best estimate of the next one.
        estimated_next = spent
        trace.write("model_response", step=steps, model=response.model,
                    stop_reason=response.stop_reason, tokens_used=tokens_used)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            answer = "".join(b.text for b in response.content if b.type == "text")
            trace.write("halt", reason="complete", steps=steps, max_steps=max_steps)
            return {"status": "COMPLETE", "steps": steps, "answer": answer,
                    "run_id": trace.run_id}

        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            trace.write("tool_request", step=steps, tool=block.name, args=block.input)
            if block.name in disabled:
                output = {"status": "error", "code": "tool_disabled", "tool": block.name}
            elif block.name in WRITE_TOOLS and not approved(block.name, block.input):
                trace.write("tool_blocked", tool=block.name,
                            code="awaiting_human_approval")
                output = {"status": "blocked", "code": "awaiting_human_approval",
                          "tool": block.name}
            else:
                output = dispatch(block.name, block.input, trace)
                if output["status"] == "error":
                    failures[block.name] = failures.get(block.name, 0) + 1
                    if failures[block.name] >= FAILURE_LIMIT:
                        disabled.add(block.name)
                        trace.write("circuit_open", tool=block.name,
                                    failures=failures[block.name])
                else:
                    failures[block.name] = 0
            trace.write("tool_result", step=steps, tool=block.name,
                        status=output["status"], code=output.get("code"))
            results.append({"type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(output)})
        messages.append({"role": "user", "content": results})

    trace.write("halt", reason="step_cap", steps=steps, max_steps=max_steps)
    return {"status": "INCOMPLETE", "reason": "step_cap", "steps": steps,
            "answer": None, "run_id": trace.run_id}


if __name__ == "__main__":
    print(run_agent("What has been published on olaparib in ovarian carcinoma?"))
