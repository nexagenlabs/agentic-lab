"""Stage 1: a single model call. Not an agent yet: it cannot do anything.

Every stage file stands alone. Nothing here imports from another stage, so
you can type this page and run it on a machine that holds nothing else.
"""

import os

from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = os.environ.get("AGENT_MODEL", "claude-sonnet-5")

response = client.messages.create(
    model=MODEL,
    max_tokens=1024,
    messages=[{"role": "user", "content": "What is ivermectin used for?"}],
)
print(response.content[0].text)
