"""
Hand-written lexer for the rule-based language.

Produces a flat list of tokens for the parser. The token vocabulary
(over the alphabet defined in §2.2 of the brief, plus the `State`
keyword from §2.3) is:

    RULE   IF   THEN   AND   STATE
    COLON  GT   LT     EQ
    ID     INT
    NEWLINE  EOF

Constraints (per §2.3):
- Identifiers: lowercase letters, digits, underscores; must start
  with a lowercase letter. Pattern: [a-z][a-z0-9_]*.
- Integers: base-10, non-negative. Pattern: [0-9]+.
- Keywords are case-sensitive. `rule`, `if`, `then`, `AND`, `State`.
- Spaces, tabs, and newlines are all ignored (§2.3: "Extra whitespace
  (spaces and blank lines) should be ignored"). The parser
  distinguishes the two State-block item shapes — `id` (active fact)
  vs `id = value` (variable assignment) — by peeking at the token
  after an identifier rather than by relying on newline separators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List


# --- Token types ------------------------------------------------------------

# Keywords.
TOK_RULE = "RULE"
TOK_IF = "IF"
TOK_THEN = "THEN"
TOK_AND = "AND"
TOK_STATE = "STATE"

# Punctuation / operators.
TOK_COLON = "COLON"
TOK_GT = "GT"
TOK_LT = "LT"
TOK_EQ = "EQ"

# Literals.
TOK_ID = "ID"
TOK_INT = "INT"

# Structural.
TOK_EOF = "EOF"


# Keyword table. Note: case-sensitive lookup.
_KEYWORDS = {
    "rule": TOK_RULE,
    "if": TOK_IF,
    "then": TOK_THEN,
    "AND": TOK_AND,
    "State": TOK_STATE,
}


@dataclass(frozen=True)
class Token:
    """A lexical token with source position for diagnostics."""

    type: str
    value: str  # raw source text (for ID/INT) or fixed lexeme (for keywords)
    line: int
    col: int

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r}, line={self.line}, col={self.col})"


class LexError(Exception):
    """Raised on an unrecognized character or malformed token."""

    def __init__(self, line: int, col: int, msg: str) -> None:
        super().__init__(f"LexError at line {line}, col {col}: {msg}")
        self.line = line
        self.col = col
        self.msg = msg


class Lexer:
    """Single-pass, position-tracked tokenizer.

    Usage:
        tokens = Lexer(source).tokenize()
    """

    def __init__(self, source: str) -> None:
        self.src = source
        self.pos = 0  # index into self.src
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    # --- Driver -------------------------------------------------------------

    def tokenize(self) -> List[Token]:
        """Lex the full source. Returns the token list ending in EOF."""
        while self.pos < len(self.src):
            ch = self.src[self.pos]

            # All whitespace (spaces, tabs, newlines, carriage
            # returns) is ignored; we just track line/col for
            # diagnostics.
            if ch == " " or ch == "\t":
                self._advance()
                continue
            if ch == "\n":
                self.pos += 1
                self.line += 1
                self.col = 1
                continue
            if ch == "\r":
                # Handle CR or CRLF as a single newline.
                self.pos += 1
                if self.pos < len(self.src) and self.src[self.pos] == "\n":
                    self.pos += 1
                self.line += 1
                self.col = 1
                continue

            # Punctuation / operators.
            if ch == ":":
                self._emit(TOK_COLON, ":")
                self._advance()
                continue
            if ch == ">":
                self._emit(TOK_GT, ">")
                self._advance()
                continue
            if ch == "<":
                self._emit(TOK_LT, "<")
                self._advance()
                continue
            if ch == "=":
                self._emit(TOK_EQ, "=")
                self._advance()
                continue

            # Identifiers / keywords. Per spec, must start with a
            # lowercase letter. `State` keyword starts with uppercase
            # `S`, so we accept an uppercase-starting word only when it
            # exactly equals `State` or `AND`.
            if ch.islower():
                self._read_word()
                continue
            if ch.isupper():
                self._read_uppercase_word()
                continue

            # Integers.
            if ch.isdigit():
                self._read_int()
                continue

            raise LexError(self.line, self.col, f"unexpected character {ch!r}")

        self._emit(TOK_EOF, "")
        return self.tokens

    # --- Token builders -----------------------------------------------------

    def _read_word(self) -> None:
        """Lex a lowercase-starting identifier or keyword."""
        start_line, start_col = self.line, self.col
        start = self.pos
        # First char known to be lowercase letter; subsequent chars may
        # be lowercase letters, digits, or underscores.
        while self.pos < len(self.src):
            c = self.src[self.pos]
            if c.islower() or c.isdigit() or c == "_":
                self._advance()
            else:
                break
        lexeme = self.src[start:self.pos]
        ttype = _KEYWORDS.get(lexeme, TOK_ID)
        self.tokens.append(Token(ttype, lexeme, start_line, start_col))

    def _read_uppercase_word(self) -> None:
        """Lex an uppercase-starting token.

        Only `AND` and `State` are valid uppercase-starting lexemes.
        Anything else is a lex error (the spec restricts identifiers to
        lowercase starts).
        """
        start_line, start_col = self.line, self.col
        start = self.pos
        while self.pos < len(self.src):
            c = self.src[self.pos]
            if c.isalpha() or c.isdigit() or c == "_":
                self._advance()
            else:
                break
        lexeme = self.src[start:self.pos]
        if lexeme in _KEYWORDS:
            self.tokens.append(Token(_KEYWORDS[lexeme], lexeme, start_line, start_col))
        else:
            raise LexError(
                start_line,
                start_col,
                f"invalid identifier or keyword {lexeme!r} "
                f"(identifiers must start with a lowercase letter)",
            )

    def _read_int(self) -> None:
        """Lex a non-negative integer literal."""
        start_line, start_col = self.line, self.col
        start = self.pos
        while self.pos < len(self.src) and self.src[self.pos].isdigit():
            self._advance()
        lexeme = self.src[start:self.pos]
        self.tokens.append(Token(TOK_INT, lexeme, start_line, start_col))

    # --- Bookkeeping --------------------------------------------------------

    def _advance(self) -> None:
        """Advance position one character, updating line/col counters."""
        self.pos += 1
        self.col += 1

    def _emit(self, ttype: str, lexeme: str) -> None:
        """Append a token at the current position."""
        self.tokens.append(Token(ttype, lexeme, self.line, self.col))
