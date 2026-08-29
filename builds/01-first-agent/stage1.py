"""Stage 1: a single model call. Not an agent yet: it cannot do anything."""

from anthropic import Anthropic
from config import MODEL

if __name__ == "__main__":
    client = Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": "Name three PARP inhibitors."}],
    )
    print(response.content[0].text)
