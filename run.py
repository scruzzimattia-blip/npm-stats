#!/usr/bin/env python3
"""Entry point for NPM Monitor application."""

import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from src.app import main

if __name__ == "__main__":
    main()
