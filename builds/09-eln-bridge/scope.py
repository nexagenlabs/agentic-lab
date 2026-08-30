"""Least privilege, expressed as an object the client cannot be built without.

A connector with a key that can read and write every project in the notebook
is a connector whose blast radius is the notebook. The scope names one project
and the record types it may touch, and every read and every write checks it
before a request is formed, so an out-of-scope identifier never becomes an
HTTP call that a server-side permission then has to decline.

Checking client-side is not a security boundary and is not offered as one. The
server's permissions are the boundary. This is the cheaper thing that catches
the realistic failure, which is an agent following a record identifier out of
the project it was pointed at because the identifier was sitting in a body of
text it read.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScopeError(RuntimeError):
    """The request is outside what this client may touch.

    Raised rather than returned, because it halts before any request is formed
    and before any model sees anything. ``as_dict`` is here for the callers
    that do feed a result back into a model's context, which must receive a
    structured object rather than a sentence about what went wrong.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail

    def as_dict(self) -> dict[str, Any]:
        return {"status": "REFUSED", "code": self.code, "detail": self.detail}


class Scope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project: str = Field(min_length=1)
    record_types: tuple[str, ...] = Field(min_length=1)

    def check_record_type(self, record_type: str) -> None:
        if record_type not in self.record_types:
            raise ScopeError(
                "record_type_out_of_scope",
                f"this client may touch {list(self.record_types)} in project "
                f"{self.project!r}, and {record_type!r} is not one of them",
            )

    def check_project(self, project: str) -> None:
        if project != self.project:
            raise ScopeError(
                "project_out_of_scope",
                f"this client is scoped to project {self.project!r} and the "
                f"request names {project!r}",
            )

    def check(self, project: str, record_type: str) -> None:
        self.check_project(project)
        self.check_record_type(record_type)
