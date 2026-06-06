"""
Resolves the project root directory for both source and PyInstaller frozen builds.
Import ROOT from here instead of computing it relative to __file__.
"""

import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    # Running as a PyInstaller exe — root is next to the executable
    ROOT = Path(sys.executable).parent
else:
    ROOT = Path(__file__).parent.parent
