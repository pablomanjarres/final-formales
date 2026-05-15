"""
Command-line entry point for the rule-based language.

Usage:
    python -m rules.cli <input-file>

(or via the thin wrapper at the project root:)

    python run.py <input-file>

Pipeline:
    1. Read source from disk.
    2. Lex into tokens.
    3. Parse into (Program, vars, facts).
    4. Run the interpreter to a fixed point.
    5. Print the sorted activated facts (or `(no output)` if empty).
    6. Print static-analysis messages (one per line).

Exit codes:
    0 — success
    1 — lex or parse error (a one-line diagnostic is written to stderr;
        no Python traceback is shown)
"""

from __future__ import annotations

import sys
from typing import List

from .analyzer import analyze
from .interpreter import Environment, evaluate
from .lexer import LexError, Lexer
from .parser import ParseError, parse


def run(source: str) -> List[str]:
    """Run the full pipeline on a source string.

    Returns the list of output lines (already in the correct order:
    activated facts or `(no output)`, then analysis messages).

    Raises `LexError` or `ParseError` on malformed input. Callers can
    decide how to render these.
    """
    tokens = Lexer(source).tokenize()
    program, vars_, facts = parse(tokens)
    initial_facts = set(facts)
    env = Environment(vars=dict(vars_), facts=set(facts))
    evaluate(program, env)
    # The output is the set of facts *activated by rule execution*,
    # excluding facts that were already in the initial state. See the
    # additional chain test case in the brief (p.9): initial fact `a`
    # does not appear in the output even though it's a member of the
    # final fact set.
    activated = env.facts - initial_facts

    lines: List[str] = []
    if not activated:
        lines.append("(no output)")
    else:
        # Lexicographic sort (§2.6).
        for fact in sorted(activated):
            lines.append(fact)

    # Analysis messages follow execution output (§2.6).
    lines.extend(analyze(program, vars_))
    return lines


def main(argv: List[str]) -> int:
    """CLI entry point. Returns a process exit code."""
    if len(argv) != 2:
        print("usage: python run.py <input-file>", file=sys.stderr)
        return 1
    path = argv[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        print(f"error: cannot read {path}: {e}", file=sys.stderr)
        return 1
    try:
        lines = run(source)
    except (LexError, ParseError) as e:
        print(str(e), file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
