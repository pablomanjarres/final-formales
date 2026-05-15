#!/usr/bin/env python3
"""
Diff-based test runner for the rule-based language project.

For every `tests/cases/*.in` file, invokes the CLI as a subprocess,
captures stdout, and compares byte-for-byte with the sibling
`*.expected` file. Prints a per-test status line and a pass/fail
summary; exits with code 0 if all tests pass, 1 otherwise.

Usage:
    python tests/run_tests.py
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


# Repository root: parent of the directory containing this script.
ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = ROOT / "tests" / "cases"
RUN_PY = ROOT / "run.py"


def discover_cases() -> List[Path]:
    """Find all .in files in the cases directory, sorted by name."""
    return sorted(CASES_DIR.glob("*.in"))


def run_case(in_path: Path) -> Tuple[bool, str, str]:
    """Run the CLI on `in_path` and compare output to the .expected file.

    Returns (passed, actual_stdout, expected_stdout).
    """
    expected_path = in_path.with_suffix(".expected")
    expected = expected_path.read_text(encoding="utf-8")
    # Force unbuffered, predictable output. Use the same Python that
    # invoked this script (sys.executable) for cross-platform safety.
    proc = subprocess.run(
        [sys.executable, str(RUN_PY), str(in_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    actual = proc.stdout
    # Treat the test as passing iff stdout matches exactly. Note: we
    # normalize trailing whitespace by comparing rstripped versions —
    # the print() loop in the CLI inserts a trailing newline after the
    # last line, which is also how the .expected files are stored.
    passed = (actual == expected) and (proc.returncode == 0)
    return passed, actual, expected


def main() -> int:
    cases = discover_cases()
    if not cases:
        print(f"No test cases found in {CASES_DIR}", file=sys.stderr)
        return 1

    n_pass = 0
    n_fail = 0
    failures: List[Tuple[str, str, str]] = []

    for in_path in cases:
        name = in_path.stem
        passed, actual, expected = run_case(in_path)
        if passed:
            print(f"PASS  {name}")
            n_pass += 1
        else:
            print(f"FAIL  {name}")
            n_fail += 1
            failures.append((name, expected, actual))

    print()
    print(f"Results: {n_pass} passed, {n_fail} failed (out of {len(cases)})")

    if failures:
        print()
        for name, expected, actual in failures:
            print(f"--- {name}: expected ---")
            print(expected, end="" if expected.endswith("\n") else "\n")
            print(f"--- {name}: actual ---")
            print(actual, end="" if actual.endswith("\n") else "\n")
            print()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
