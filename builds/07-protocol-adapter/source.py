"""Reading a published protocol, and the identity it does or does not carry.

The front matter is where the record of provenance lives: the DOI and the line
the work was done in. A protocol that names its line without an RRID is not
rejected here, because a published paper is not ours to fix, but the omission
is carried forward so the report can name it. That absence is the useful
output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from models import AdapterError

FRONT_MATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)


@dataclass(frozen=True)
class SourceProtocol:
    """One published protocol, as read off disk."""

    path: Path
    doi: str
    title: str
    cell_line: str
    cell_line_rrid: str | None
    body: str

    @property
    def declares_identity(self) -> bool:
        """Does the source name its line in a way anyone can check?"""
        return bool(self.cell_line and self.cell_line_rrid)

    def quotes(self, evidence: str) -> bool:
        """Does this sentence actually appear in the protocol?

        Whitespace is normalised, because the body is wrapped and a quotation
        that spans a line break is still a quotation. Nothing else is
        normalised: a paraphrase is not a quote and must not pass for one.
        """
        if not evidence:
            return False
        haystack = " ".join(self.body.split()).lower()
        needle = " ".join(evidence.split()).lower()
        return needle in haystack


def _front_matter_value(block: str, key: str) -> str | None:
    for line in block.splitlines():
        name, _, value = line.partition(":")
        if name.strip() == key:
            return value.strip() or None
    return None


def load_protocol(path: str | Path) -> SourceProtocol:
    """Read a protocol, or refuse with a code rather than a sentence."""
    path = Path(path)
    if not path.exists():
        raise AdapterError("protocol_missing", f"no protocol at {path}")

    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = FRONT_MATTER_RE.match(text)
    if match is None:
        raise AdapterError(
            "no_front_matter",
            f"{path.name} carries no front matter, so it names no DOI and no "
            "cell line. An adaptation with no provenance is not an adaptation.",
        )

    block, body = match.groups()
    doi = _front_matter_value(block, "doi")
    cell_line = _front_matter_value(block, "cell_line")
    if not doi or not cell_line:
        raise AdapterError(
            "incomplete_front_matter",
            f"{path.name} must state both doi and cell_line; got doi={doi!r}, "
            f"cell_line={cell_line!r}",
        )

    return SourceProtocol(
        path=path,
        doi=doi,
        title=_front_matter_value(block, "title") or path.stem,
        cell_line=cell_line,
        cell_line_rrid=_front_matter_value(block, "cell_line_rrid"),
        body=body,
    )
