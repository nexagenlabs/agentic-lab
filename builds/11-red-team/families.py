"""The family set, open, because the chapter's failure account demanded it.

Chapter 10 ends with a harness that scored 1.0 across thirty-one faults and
missed one it had never conceived of: a preprint and its published version
counted as two papers, because deduplication worked on identifiers and the two
have different ones. Nobody wrote a bad check. There was no check, because
there was no family, because the list of families was a list somebody finished
writing one afternoon.

``harness.Fault`` has a closed ``Literal`` naming the four families the chapter
names, and that is what the book prints, so it stays exactly as printed.
``OpenFault`` here carries the same five fields with ``family`` as a string
validated against a registry that can be added to at runtime. Both work with
``run_red_team``, which takes ``list[Fault]`` in the printed signature and does
not check it, because Python does not.

The registry is not a clever mechanism and it is not meant to be. It is a
dictionary plus the requirement that adding to it means writing down why the
family exists, so the next person inherits the argument rather than the entry.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

# The four the chapter names, plus the one its own failure account produced.
# The `why` is required: a family with no stated reason is a category somebody
# will delete during a tidy-up, and this is the file where that would be a
# mistake.
_FAMILIES: dict[str, str] = {
    "fabrication": (
        "References that do not exist, or that exist and say something else. "
        "Characteristically a real journal with a nonexistent title, which is "
        "why checking that a citation looks right catches nothing."
    ),
    "numeric": (
        "Units, transpositions, off-by-one labels and silent type coercion. "
        "The failure that produces a plausible number rather than an error."
    ),
    "drift": (
        "A run that walks away from its instruction while every individual "
        "step remains defensible."
    ),
    "loop": (
        "Repetition, non-termination, and step caps reached with work "
        "outstanding."
    ),
    "identity": (
        "Two records that are one thing. A preprint and its published "
        "version, one record under two identifier schemes, the same title "
        "differing in whitespace and case. This family exists because the "
        "chapter's harness scored 1.0 without it and was wrong: "
        "deduplication worked on identifiers, and the two versions of a "
        "paper have different identifiers. It is the family nobody conceives "
        "of until it has cost them something."
    ),
}


class UnknownFamily(ValueError):
    """A fault named a family nobody has registered.

    Raised rather than accepted. The point of the registry is that adding a
    family is a deliberate act with a written reason, and silently accepting
    an unregistered string would make it an accident.
    """


def register_family(name: str, why: str) -> None:
    """Add a family at runtime. No model is edited, and no enum is widened."""
    if not name or not name.strip():
        raise UnknownFamily("a family needs a name")
    if not why or len(why.split()) < 5:
        raise UnknownFamily(
            f"registering {name!r} requires a written reason for the family "
            "existing. The chapter's failure was a missing category, not a "
            "missing check, and a category with no argument behind it is the "
            "next one somebody quietly drops."
        )
    _FAMILIES[name] = why


def known_families() -> tuple[str, ...]:
    return tuple(sorted(_FAMILIES))


def why_family_exists(name: str) -> str:
    if name not in _FAMILIES:
        raise UnknownFamily(f"{name!r} is not a registered family")
    return _FAMILIES[name]


class OpenFault(BaseModel):
    """``harness.Fault`` with the family opened up. Same five fields.

    Deliberately not a subclass. ``Fault`` is the printed listing and a reader
    typing it from the page gets a closed ``Literal``; inheriting from it would
    make the open behaviour look like something the book printed.
    """

    model_config = ConfigDict(extra="forbid")

    fault_id: str
    family: str
    description: str
    inject: Callable[[Any], Any]
    should_be_caught_by: str

    @field_validator("family")
    @classmethod
    def family_is_registered(cls, value: str) -> str:
        if value not in _FAMILIES:
            raise UnknownFamily(
                f"{value!r} is not a registered family. Call "
                f"register_family({value!r}, why) first. Known: "
                f"{', '.join(known_families())}"
            )
        return value

    @field_validator("fault_id")
    @classmethod
    def identifier_carries_the_family(cls, value: str) -> str:
        """``Report`` parses the family out of the identifier, because the
        printed ``FaultResult`` has no field for one."""
        if "-" not in value:
            raise ValueError(
                f"fault ids are <family>-<n>, and {value!r} is not, so the "
                "report would attribute it to the wrong family"
            )
        return value
