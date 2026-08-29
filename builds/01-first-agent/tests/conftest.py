"""Put the build directory on the path so the tests import it as the reader
does, by running the files in place.

Build 01 and Build 02 both carry modules called ``agent``, ``config`` and
``stub_client``, because each build must stand alone for a reader who opens
only that folder. Python caches imported modules by name, so in a single
pytest process covering both builds, whichever build is collected first would
otherwise hand its modules to the second one, and the second build's tests
would quietly measure the wrong code while still passing. Dropping the other
build's modules before this build imports its own is what keeps the two
apart. ``--import-mode=importlib`` in pyproject.toml settles the test module
names; it does not settle these.
"""

import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parents[1]
BUILDS_ROOT = BUILD_DIR.parent

for name, module in list(sys.modules.items()):
    origin = getattr(module, "__file__", None)
    if not origin:
        continue
    path = Path(origin).resolve()
    if BUILDS_ROOT in path.parents and BUILD_DIR not in path.parents:
        del sys.modules[name]

sys.path.insert(0, str(BUILD_DIR))
