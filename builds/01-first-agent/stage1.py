"""Stage 1: a single model call. Not an agent yet: it cannot do anything.

Every stage file stands alone. Nothing here imports from another stage, so
you can type this page and run it on a machine that holds nothing else.
"""

import os

from anthropic import Anthropic

client = Anthropic()
response = client.messages.create(
    model=os.environ.get("AGENT_MODEL", "claude-opus-5"),
    max_tokens=1024,
    messages=[{"role": "user", "content": "Name three PARP inhibitors."}],
)
print(response.content[0].text)
