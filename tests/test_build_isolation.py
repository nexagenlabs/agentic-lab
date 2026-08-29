"""The cross-build import collision, as a test rather than as a habit.

Builds deliberately share module names, because each folder must stand alone
for a reader. Three separate sessions have shipped a test that silently
imported a different build's module of the same name. The repository root
conftest.py makes that impossible; these tests assert that it does, and that
a build added later cannot opt out of it.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BUILDS_ROOT = REPO_ROOT / "builds"

GUARD_TEST = "def test_this_build_imported_its_own_modules"


def implemented_builds() -> list[Path]:
    """Build folders that carry tests, so are subject to the invariant."""
    return sorted(p for p in BUILDS_ROOT.iterdir() if (p / "tests").is_dir())


def test_module_names_really_do_collide_across_builds():
    """If this ever stops being true the mechanism is still cheap, but the
    reason for it should be visible rather than folklore."""
    owners: dict[str, list[str]] = defaultdict(list)
    for build in implemented_builds():
        for module in build.glob("*.py"):
            owners[module.name].append(build.name)
    shared = {name: sorted(b) for name, b in owners.items() if len(b) > 1}
    assert shared, (
        "No module name is shared between builds any more. The root "
        "conftest.py isolation is now belt and braces rather than load "
        "bearing; say so there before removing it."
    )


def test_at_most_one_build_is_on_the_path():
    on_path = [
        p for p in sys.path
        if BUILDS_ROOT in Path(p).resolve().parents
        or Path(p).resolve().parent == BUILDS_ROOT
    ]
    assert len(on_path) <= 1, (
        f"More than one build folder is importable at once: {on_path}. "
        "A bare `import models` here would resolve by accident."
    )


def test_no_build_module_is_importable_from_a_root_test():
    """These tests belong to no build, so no build's modules should be live."""
    leaked = sorted(
        name for name, module in sys.modules.items()
        if getattr(module, "__file__", None)
        and Path(module.__file__).resolve().parent.parent == BUILDS_ROOT
    )
    assert not leaked, f"Build modules left in sys.modules: {leaked}"


@pytest.mark.parametrize(
    "build", implemented_builds(), ids=lambda p: p.name
)
def test_every_build_ships_the_guard(build: Path):
    """A new build cannot quietly skip the check that caught this three
    times, because this test fails until it carries one."""
    conftest = build / "tests" / "conftest.py"
    assert conftest.exists(), f"{build.name} has no tests/conftest.py"

    sources = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((build / "tests").glob("test_*.py"))
    )
    assert GUARD_TEST in sources, (
        f"{build.name} has no {GUARD_TEST.split()[1]}. Every build asserts "
        "that the modules it imported came out of its own folder."
    )
