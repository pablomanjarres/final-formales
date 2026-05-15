#!/usr/bin/env python3
"""
Thin wrapper around `rules.cli.main` so users can run the program
from the project root with `python run.py <input-file>`.
"""

import sys

from rules.cli import main


if __name__ == "__main__":
    sys.exit(main(sys.argv))
