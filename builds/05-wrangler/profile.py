"""Stage one: look at the file before parsing it.

The agent sees fifteen lines and a shape summary, never the whole export. That
bound is not politeness about tokens. A model shown ten thousand rows starts
forming opinions about the values, and the one thing this build must never do
is let a model near a number.
"""

import csv
from pathlib import Path


def _sniff(head: list[str]) -> str | None:
    """Guess the delimiter, or give up quietly.

    csv.Sniffer raises on a great many real exports: ragged preambles, merged
    title cells, a single column. A guess is a convenience, so failing to make
    one is not an error and must not stop the profile being taken.
    """
    sample = "\n".join(head)
    if not sample.strip():
        return None
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except (csv.Error, TypeError):
        return None


def profile(path: Path) -> dict:
    raw = path.read_text(errors="replace").splitlines()[:15]
    return {
        "filename": path.name,
        "head": raw,
        "n_lines": sum(1 for _ in path.open()),
        "delimiter_guess": _sniff(raw),   # returns None rather than raising
    }
