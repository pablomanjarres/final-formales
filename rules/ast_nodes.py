"""AST node definitions for the rule-based language.

Matches the canonical structure defined in section 2.4 of the project brief:
Program > Rule > Condition (AndCond | atomic) where atomic is Comparison | Fact.
Action wraps the identifier of the fact a rule activates.
"""

from dataclasses import dataclass, field
from typing import List, Union


@dataclass(frozen=True)
class Comparison:
    """Atomic condition: variable compared against an integer literal."""
    ident: str
    op: str  # ">" | "<" | "="
    value: int


@dataclass(frozen=True)
class Fact:
    """Atomic condition: an identifier that is true iff the fact is active."""
    ident: str


@dataclass(frozen=True)
class AndCond:
    """Conjunction of two conditions."""
    left: "Cond"
    right: "Cond"


Cond = Union[AndCond, Comparison, Fact]


@dataclass(frozen=True)
class Action:
    """The fact a rule activates when fired."""
    ident: str


@dataclass
class Rule:
    """A named rule: condition implies action."""
    name: str
    cond: Cond
    action: Action


@dataclass
class Program:
    """A list of rules in source order."""
    rules: List[Rule] = field(default_factory=list)


def flatten_and(cond: Cond) -> List[Union[Comparison, Fact]]:
    """Flatten an AndCond tree into the list of atomic conjuncts.

    Useful for analyzer normalization (AND is associative + commutative, so
    two rules with conjuncts in different orders are semantically equal).
    """
    if isinstance(cond, AndCond):
        return flatten_and(cond.left) + flatten_and(cond.right)
    return [cond]


def canonical_cond_key(cond: Cond) -> tuple:
    """Order-independent key for a condition.

    Two conditions yield the same key iff they are equal modulo
    reordering of AND conjuncts.
    """
    atoms = flatten_and(cond)
    # Each atom is a frozen dataclass, so a tuple of (type-name, fields) is hashable.
    keyed = []
    for a in atoms:
        if isinstance(a, Comparison):
            keyed.append(("cmp", a.ident, a.op, a.value))
        else:  # Fact
            keyed.append(("fact", a.ident))
    return tuple(sorted(keyed))
