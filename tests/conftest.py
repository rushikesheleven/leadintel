"""pytest configuration."""

import os
import sys

# Make sure the src layout is importable during tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
