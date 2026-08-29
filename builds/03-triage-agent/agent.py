"""The loop, carried over from Build 02, with one change that matters.

Build 02 returned the model's final text. A screening run needs a structured
verdict, so this loop parses the final message as JSON and returns an object.
A reply that is not JSON is not a verdict, and it is reported as a failure
rather than salvaged: ``screen_corpus`` then records the record as a gap,
which is the honest outcome. Guessing at a malformed verdict is exactly the
behaviour this build exists to argue against.

Screening offers no tools. The agent is judging a record it already holds, so
there is nothing for it to go and fetch, and ``max_steps=4`` is generous.
"""

import json
import time
from typing import Any

from anthropic import Anthropic, APIConnectionError, APIError
from config import MODEL
from dispatch import dispatch
from tracing import Trace

MAX_STEPS = 20
MAX_TOKENS = 2048

# The ceiling a run may spend. Checked before a call, never after.
TOKEN_BUDGET = 100_000

# Three consecutive failures from one tool is not bad luck, it is a broken
# tool. Disable it rather than spend the rest of the run rediscovering that.
FAILURE_LIMIT = 3

# Status codes that mean the same request may work in a moment. Everything
# else, a 400 above all, means the request itself is wrong and always will be.
TRANSIENT_STATUS = frozenset({408, 409, 429, 500, 502, 503, 504})


def is_transient(error: APIError) -> bool:
    """A dropped connection never reached a server, so it has no status code
    to read. Everything else is judged on the code it came back with."""
    if isinstance(error, APIConnectionError):
        return True
    return getattr(error, "status_code", None) in TRANSIENT_STATUS


def parse_answer(text: str) -> dict[str, Any] | None:
    """Read the model's final message as one JSON object, or return None.

    Models are asked for bare JSON and sometimes wrap it in a code fence
    anyway. Stripping a fence is worth doing because it is unambiguous.
    Anything beyond that is guessing at what was meant, which is how a
    malformed verdict becomes a recorded one.
    """
    body = text.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[-1] if "\n" in body else ""
        if body.rstrip().endswith("```"):
            body = body.rstrip()[: -len("```")]
    try:
        parsed = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def run_agent(
    task: str,
    max_steps: int = MAX_STEPS,
    *,
    tools: list[dict[str, Any]] | None = None,
    client: Any = None,
    trace: Trace | None = None,
    run_dir: str = "runs",
    token_budget: int = TOKEN_BUDGET,
    backoff_s: float = 2.0,
) -> dict[str, Any]:
    """Run the loop until the model stops, the cap is reached, or the budget
    runs out. A run that hits the cap returns INCOMPLETE with no answer."""
    client = client or Anthropic()
    trace = trace or Trace(run_dir)
    tools = tools or []
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    steps = 0
    tokens_used = 0
    # Nothing has been measured yet, so nothing is assumed. The first call is
    # the one that produces the estimate every later call is judged against.
    estimated_next = 0
    retries = 0
    failures: dict[str, int] = {}
    disabled: set[str] = set()
    trace.write("run_start", model=MODEL, max_steps=max_steps,
                token_budget=token_budget, tools=[t["name"] for t in tools])

    while steps < max_steps:
        # Before the call, not after: a budget checked afterwards is one that
        # has already been spent.
        if tokens_used + estimated_next > token_budget:
            trace.write("halt", reason="budget", steps=steps,
                        max_steps=max_steps, tokens_used=tokens_used)
            return {"status": "INCOMPLETE", "reason": "budget", "steps": steps,
                    "answer": None, "run_id": trace.run_id}

        steps += 1
        offered = [tool for tool in tools if tool["name"] not in disabled]
        trace.write("model_call", step=steps, model=MODEL)
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=MAX_TOKENS, tools=offered, messages=messages,
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
            text = "".join(b.text for b in response.content if b.type == "text")
            answer = parse_answer(text)
            if answer is None:
                trace.write("halt", reason="unparsable_answer", steps=steps,
                            max_steps=max_steps)
                return {"status": "FAILED", "code": "unparsable_answer",
                        "steps": steps, "answer": None, "run_id": trace.run_id}
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
