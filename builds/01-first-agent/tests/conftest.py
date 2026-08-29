"""Put the build directory on the path so the tests import it as the reader
does, by running the files in place."""

import sys
from pathlib import Path

BUILD_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUILD_DIR))
