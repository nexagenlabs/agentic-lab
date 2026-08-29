"""Cross-build import isolation, owned in one place.

Every build is a flat folder of top-level modules that a reader can run in
place, so `from config import MODEL` has to work when only that one folder is
on the path. The consequence is that builds collide by name: four of them
carry `config.py`, five carry `models.py`, four carry `tracing.py`, and Python
caches modules by bare name. A single pytest process covering the whole
repository would otherwise hand one build's `models` to another build's tests,
which then pass while measuring the wrong code.

That has happened three times, in builds 02, 04 and 05, and was fixed one
instance at a time. This file removes the possibility instead. Before pytest
imports a test module, and again before each test runs, exactly one build is
active:

  * `sys.path` holds that build's folder and no other build's folder,
  * `sys.modules` holds that build's own modules and no other build's.

Modules are parked in a per-build cache rather than discarded, so a module
imported inside a test function body is the same object the test file imported
at the top. Re-importing would give a second copy of every class and
`isinstance` would quietly start lying, which is a worse failure than the one
being fixed.

None of this is book code, and no build depends on it. Each build still keeps
a two-line `tests/conftest.py` putting its own folder on the path, so a folder
copied out of the repository stands alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
BUILDS_ROOT = REPO_ROOT / "builds"

# Modules belonging to builds that are not currently active, keyed by build.
_parked: dict[Path, dict[str, object]] = {}
_active: Path | None = None


def _build_dir(path: Path) -> Path | None:
    """Which build folder, if any, does this path sit inside?"""
    try:
        rel = path.resolve().relative_to(BUILDS_ROOT)
    except (ValueError, OSError, RuntimeError):
        return None
    return BUILDS_ROOT / rel.parts[0] if rel.parts else None


def _owner(module: object) -> Path | None:
    """Which build owns this module, if it is one of a build's own modules?

    Only modules sitting directly in a build folder count. Test modules and
    conftest files are pytest's to manage, not ours.
    """
    origin = getattr(module, "__file__", None)
    if not origin:
        return None
    try:
        parent = Path(origin).resolve().parent
    except (OSError, ValueError, RuntimeError):
        return None
    return parent if _build_dir(parent) == parent else None


def _fix_sys_path(build: Path | None) -> None:
    """Leave at most one build folder on the path, at the front."""
    kept = [p for p in sys.path if _build_dir(Path(p)) is None]
    if build is not None:
        kept.insert(0, str(build))
    if kept != sys.path:
        sys.path[:] = kept


def activate(build: Path | None) -> None:
    """Make `build` the only importable build, or no build at all."""
    global _active
    if build is not None and not build.is_dir():
        build = None
    if build != _active:
        for name, module in list(sys.modules.items()):
            owner = _owner(module)
            if owner is None:
                continue
            _parked.setdefault(owner, {})[name] = module
            del sys.modules[name]
        if build is not None:
            sys.modules.update(_parked.pop(build, {}))
        _active = build
    _fix_sys_path(build)


def active_build() -> Path | None:
    """The build currently importable, for the isolation tests to assert on."""
    return _active


def pytest_collectstart(collector) -> None:
    # Fires before pytest imports the module it is about to collect, which is
    # where a test file's own top-level imports of build modules resolve.
    path = getattr(collector, "path", None)
    if path is not None:
        activate(_build_dir(Path(path)))


def pytest_runtest_setup(item) -> None:
    # And again per test, so an import inside a function body cannot resolve
    # to whichever build was collected most recently.
    activate(_build_dir(Path(item.path)))
