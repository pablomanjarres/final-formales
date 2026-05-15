"""
Recursive-descent LL(1) parser for the rule-based language.

The minimal grammar from §2.2 of the brief is left-recursive in Cond
and not factored in Atom. We use the equivalent LL(1) grammar:

    Program     -> RuleList
    RuleList    -> Rule RuleList | ε
    Rule        -> "rule" id ":" "if" Cond "then" Action
    Cond        -> Atom CondTail
    CondTail    -> "AND" Atom CondTail | ε
    Atom        -> id AtomTail
    AtomTail    -> RelOp value | ε
    RelOp       -> ">" | "<" | "="
    Action      -> id

(The `AtomTail -> ε` alternative becomes the `Fact` form; the
`AtomTail -> RelOp value` alternative becomes the `Comparison` form.)

In addition, this parser handles the optional initial-state block
from §2.3 of the brief:

    StateBlock  -> "State" ":" StateItem*
    StateItem   -> id "=" value
                 | id

The state block is *not* part of the formal grammar, but is read by
the same driver because it lives in the same input file. The parser
exposes a single entry point, `parse`, that returns a `(Program,
vars_dict, facts_set)` triple.

The lexer discards all whitespace (including newlines), so the parser
sees a clean token stream. State items are disambiguated by peeking
the token after each identifier (EQ → variable assignment, anything
else → active fact).
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from .ast_nodes import Action, AndCond, Comparison, Cond, Fact, Program, Rule
from .lexer import (
    TOK_AND,
    TOK_COLON,
    TOK_EOF,
    TOK_EQ,
    TOK_GT,
    TOK_ID,
    TOK_IF,
    TOK_INT,
    TOK_LT,
    TOK_RULE,
    TOK_STATE,
    TOK_THEN,
    Token,
)


class ParseError(Exception):
    """Raised on a syntactic mismatch with a clear, position-tagged message."""

    def __init__(self, token: Token, expected: str) -> None:
        msg = (
            f"ParseError at line {token.line}, col {token.col}: "
            f"expected {expected}, got {token.type} {token.value!r}"
        )
        super().__init__(msg)
        self.token = token
        self.expected = expected


class Parser:
    """Recursive-descent parser with 1-token lookahead."""

    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # --- Lookahead / consumption helpers ------------------------------------

    def _peek(self) -> Token:
        """Return the current token without advancing."""
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        """Consume and return the current token."""
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, ttype: str, what: str) -> Token:
        """Consume a token of the expected type or raise ParseError."""
        tok = self._peek()
        if tok.type != ttype:
            raise ParseError(tok, what)
        return self._advance()

    # --- Entry point --------------------------------------------------------

    def parse(self) -> Tuple[Program, Dict[str, int], Set[str]]:
        """Parse a complete input file.

        Returns:
            (program, vars_dict, facts_set) — the rule list and the
            (possibly empty) initial environment from the State block.
        """
        program = self._parse_program()
        vars_dict: Dict[str, int] = {}
        facts_set: Set[str] = set()
        if self._peek().type == TOK_STATE:
            vars_dict, facts_set = self._parse_state_block()
        # Anything left over after a valid program/state pair is an error.
        if self._peek().type != TOK_EOF:
            raise ParseError(self._peek(), "end of input")
        return program, vars_dict, facts_set

    # --- Rule list ----------------------------------------------------------

    def _parse_program(self) -> Program:
        """Program -> RuleList. Stops at first STATE or EOF."""
        rules: List[Rule] = []
        while True:
            tok = self._peek()
            if tok.type == TOK_RULE:
                rules.append(self._parse_rule())
            elif tok.type in (TOK_STATE, TOK_EOF):
                break
            else:
                raise ParseError(tok, "'rule', 'State', or end of input")
        return Program(rules=rules)

    def _parse_rule(self) -> Rule:
        """Rule -> "rule" id ":" "if" Cond "then" Action."""
        self._expect(TOK_RULE, "'rule'")
        name_tok = self._expect(TOK_ID, "rule name (identifier)")
        self._expect(TOK_COLON, "':'")
        self._expect(TOK_IF, "'if'")
        cond = self._parse_cond()
        self._expect(TOK_THEN, "'then'")
        action_tok = self._expect(TOK_ID, "action identifier")
        return Rule(name=name_tok.value, cond=cond, action=Action(ident=action_tok.value))

    # --- Condition / atom ---------------------------------------------------

    def _parse_cond(self) -> Cond:
        """Cond -> Atom CondTail.

        Builds a left-leaning AndCond chain so that
        `a AND b AND c` becomes `AndCond(AndCond(a, b), c)`.
        """
        node: Cond = self._parse_atom()
        while self._peek().type == TOK_AND:
            self._advance()  # consume AND
            right = self._parse_atom()
            node = AndCond(left=node, right=right)
        return node

    def _parse_atom(self) -> Cond:
        """Atom -> id (RelOp value)?.

        Distinguishes Comparison vs Fact by peeking after the id.
        """
        ident_tok = self._expect(TOK_ID, "identifier")
        nxt = self._peek()
        if nxt.type in (TOK_GT, TOK_LT, TOK_EQ):
            op_tok = self._advance()
            op = {"GT": ">", "LT": "<", "EQ": "="}[op_tok.type]
            value_tok = self._expect(TOK_INT, "integer value")
            return Comparison(ident=ident_tok.value, op=op, value=int(value_tok.value))
        return Fact(ident=ident_tok.value)

    # --- State block --------------------------------------------------------

    def _parse_state_block(self) -> Tuple[Dict[str, int], Set[str]]:
        """StateBlock -> "State" ":" StateItem*.

        Each item is either `id = value` (variable assignment) or `id`
        (active fact). The lexer discards whitespace including
        newlines; we distinguish the two item shapes by peeking the
        token after each identifier.
        """
        self._expect(TOK_STATE, "'State'")
        self._expect(TOK_COLON, "':'")
        vars_dict: Dict[str, int] = {}
        facts_set: Set[str] = set()
        while self._peek().type == TOK_ID:
            ident_tok = self._advance()
            nxt = self._peek()
            if nxt.type == TOK_EQ:
                self._advance()  # consume '='
                value_tok = self._expect(TOK_INT, "integer value")
                vars_dict[ident_tok.value] = int(value_tok.value)
            else:
                # Bare identifier — active fact.
                facts_set.add(ident_tok.value)
        return vars_dict, facts_set


def parse(tokens: List[Token]) -> Tuple[Program, Dict[str, int], Set[str]]:
    """Convenience wrapper: parse a token list end-to-end."""
    return Parser(tokens).parse()
