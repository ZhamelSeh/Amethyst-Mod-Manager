#!/usr/bin/env python3
"""Entry point for the in-progress Qt (PySide6) UI.

Parallel to src/gui.py (the Tk app). Run from src/ so the gui_qt / gui / Utils
/ Games packages import cleanly:

    ../.venv/bin/python3 run_qt.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gui_qt.app import run

if __name__ == "__main__":
    sys.exit(run())
