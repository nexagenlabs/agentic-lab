"""Put this build's folder on the path, so it stands alone.

Cross-build isolation is owned by the repository root conftest.py, which
keeps exactly one build importable at a time. This file exists so that a
reader who copies only this folder out still gets `import config` working.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
