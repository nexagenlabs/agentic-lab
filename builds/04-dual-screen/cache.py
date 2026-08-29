"""Content-addressed cache for retrieved records.

Every entry carries a SHA-256 taken over the payload it holds. That buys two
things. A re-run does not re-fetch, which is what lets the tests run with no
network at all. And a cache entry that has been edited or truncated since it
was written is detected rather than screened, because a verdict produced from
a corrupted record is worse than a verdict not produced.

This is the first appearance of the content hashing that Chapter 9 builds into
the run manifest.
"""

import hashlib
import json
from pathlib import Path
from typing import Any


class CacheError(RuntimeError):
    """A cache entry exists but cannot be trusted."""


def digest(payload: dict[str, Any]) -> str:
    """SHA-256 over the payload, canonicalised so the hash is stable.

    Sorted keys and fixed separators, because ``json.dumps`` is free to vary
    whitespace and key order between runs and a hash that changes for a
    payload that has not is worthless.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def entry_path(pmid: str, cache_dir: str | Path) -> Path:
    return Path(cache_dir) / f"{pmid}.json"


def read(pmid: str, cache_dir: str | Path) -> dict[str, Any] | None:
    """Return the cached payload, or None if this record is not cached.

    Raises ``CacheError`` if an entry is present but its hash does not match
    its payload. A miss is ordinary; a mismatch is not, and silently
    re-fetching over the top of it would hide the fact that something has been
    editing the cache.
    """
    path = entry_path(pmid, cache_dir)
    if not path.exists():
        return None

    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CacheError(f"cache entry could not be read: {path}: {error}") from error

    if "payload" not in entry or "sha256" not in entry:
        raise CacheError(f"cache entry is missing payload or sha256: {path}")

    payload = entry["payload"]
    actual = digest(payload)
    if actual != entry["sha256"]:
        raise CacheError(
            f"cache entry does not match its hash: {path}: "
            f"recorded {entry['sha256'][:12]}, computed {actual[:12]}"
        )
    return payload


def write(pmid: str, payload: dict[str, Any], cache_dir: str | Path) -> Path:
    """Write one payload to the cache with its hash, and return the path."""
    path = entry_path(pmid, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"pmid": pmid, "sha256": digest(payload), "payload": payload}
    path.write_text(json.dumps(entry, indent=2) + "\n", encoding="utf-8")
    return path
