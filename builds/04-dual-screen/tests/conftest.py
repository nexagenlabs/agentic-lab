"""Put the build directory on the path so the tests import it as the reader
does, by running the files in place.

Several builds carry modules of the same name, because each build must stand
alone for a reader who opens only that folder. Python caches by name, so a
single pytest process covering more than one build would otherwise hand the
first build modules to the second, and the second build tests would quietly
measure the wrong code while still passing.
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
