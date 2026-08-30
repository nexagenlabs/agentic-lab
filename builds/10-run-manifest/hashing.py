"""Content addressing, because a filename is a label somebody chose.

``results_final_v3.csv`` tells you what somebody hoped about a file on the
afternoon they named it. It does not tell you what is in it, whether it is the
one the run read, or whether anybody has touched it since. A digest does, and
it keeps doing so after the file has been renamed, copied to a share, emailed
and copied back.

``bytes`` is recorded next to every digest. Two reasons, and the second is the
one that repays the column. A truncated file is visible without rehashing
anything, which matters when the file is four gigabytes and the question is
being asked on a laptop. And a digest with a size beside it is a claim somebody
can falsify cheaply, which is the only kind of provenance anybody checks.

The chunked read is not premature optimisation. Instrument exports and
structure files run to hundreds of megabytes, and a manifest tool that loads
each input entirely into memory to hash it is a tool people stop running.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

# 64 KiB. Large enough that the loop is not the cost, small enough that a
# machine doing something else at the time does not notice.
CHUNK = 65536


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def hash_text(text: str) -> str:
    return hash_bytes(text.encode("utf-8"))


def canonical_json(payload: Any) -> str:
    """One serialisation, so two equal objects hash equally.

    Sorted keys and a fixed indent. Without this, a dictionary that happened to
    be built in a different order produces a different digest and a replay
    reports drift that is entirely an artefact of the writer.
    """
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def hash_json(payload: Any) -> str:
    return hash_text(canonical_json(payload))


def write_json(path: Path, payload: Any) -> str:
    """Write canonically and return the digest of what was written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    text = canonical_json(payload)
    path.write_text(text, encoding="utf-8", newline="\n")
    return hash_text(text)
