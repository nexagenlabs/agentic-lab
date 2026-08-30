"""Put this build's folder on the path, so it stands alone.

Cross-build isolation is owned by the repository root conftest.py, which
keeps exactly one build importable at a time. This file exists so that a
reader who copies only this folder out still gets `import harness` working.

The earlier builds this harness measures are never imported here. They run in
subprocesses, one build folder each, which is why this build can reach five
others without breaking the invariant the root conftest.py enforces.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
