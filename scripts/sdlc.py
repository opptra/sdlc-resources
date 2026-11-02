#!/usr/bin/env python3
"""Compatibility entry for callers that still run scripts/sdlc.py. The command is odlc."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from odlc import main

if __name__ == "__main__":
    raise SystemExit(main())
