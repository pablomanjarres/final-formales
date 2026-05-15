"""
Fixed-point interpreter for the rule-based language.

Semantics (per §2.5 of the brief):

- An environment has two parts: a variable map (id -> int) and a set
  of active facts (ids).
- A Comparison(x, op, v) is true iff the variable `x` is defined and
  the comparison with `v` holds.
- A Fact(x) is true iff `x` is currently in the active fact set.
- An AndCond(c1, c2) is true iff both subconditions are true.
- A rule is *applicable* iff its condition evaluates to true under the
  current environment.
- Execution is iterative: repeatedly collect actions of all applicable
  rules, union their identifiers into the fact set, and stop when no
  new fact is added. Variables are never mutated.

Determinism (§2.5): the order in which rules are evaluated does not
affect the final fact set, since each iteration evaluates *all* rules
against the same snapshot before adding new facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Set

from .ast_nodes import AndCond, Comparison, Cond, Fact, Program


@dataclass
class Environment:
    """Execution environment: variables and active facts.

    Variables and facts live in independent namespaces (§2.5).
    """

    vars: Dict[str, int] = field(default_factory=dict)
    facts: Set[str] = field(default_factory=set)


def evaluate_cond(cond: Cond, env: Environment) -> bool:
    """Recursively evaluate a condition under the given environment."""
    if isinstance(cond, AndCond):
        return evaluate_cond(cond.left, env) and evaluate_cond(cond.right, env)
    if isinstance(cond, Comparison):
        if cond.ident not in env.vars:
            # Undefined variable — condition is false. The static
            # analyzer is responsible for flagging the rule as
            # potentially inactive.
            return False
        x = env.vars[cond.ident]
        if cond.op == ">":
            return x > cond.value
        if cond.op == "<":
            return x < cond.value
        if cond.op == "=":
            return x == cond.value
        # Unreachable — the parser only produces these three operators.
        raise ValueError(f"unknown comparison operator: {cond.op!r}")
    if isinstance(cond, Fact):
        return cond.ident in env.facts
    raise TypeError(f"unknown condition node type: {type(cond).__name__}")


def evaluate(program: Program, env: Environment) -> Set[str]:
    """Run the program to a fixed point and return the activated fact set.

    The initial fact set in `env` is included in the result. `env` is
    mutated in place; callers that need to preserve the initial state
    should pass a fresh `Environment`.
    """
    # Order-independence: each iteration evaluates every rule against
    # the same snapshot, so the result is deterministic.
    while True:
        added = False
        # Snapshot the current fact set so all rules in this iteration
        # see the same view (rather than newly-added facts leaking in
        # mid-iteration, which would make output order-dependent).
        new_facts: Set[str] = set()
        for rule in program.rules:
            if evaluate_cond(rule.cond, env):
                if rule.action.ident not in env.facts:
                    new_facts.add(rule.action.ident)
        if new_facts:
            env.facts.update(new_facts)
            added = True
        if not added:
            break
    return env.facts
