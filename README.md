# Rule-Based Language with Execution and Analysis

Final project for **SI2002 Formal Languages / ST0270 Formal Languages and Compilers / CM0081 Formal Languages and Automata**.

This system defines, processes, and executes a small rule-based language of the form `rule <id>: if <cond> then <action>`. The pipeline is a textbook compiler frontend plus a fixed-point interpreter and a static analyzer:

```
source text → Lexer → Parser → AST → Interpreter (fixed point) → output
                                  ↘ Analyzer → diagnostics
```

## Group members

- Pablo Manjarres
- Valentina Barbosa

## Versions

- **Operating system:** macOS 26.4.1 (developed on)
- **Programming language:** Python 3.9.6
- **Third-party libraries:** none (standard library only)
- **Parser generators:** none (recursive-descent LL(1), hand-written, as required by §6 of the brief)
- **Build tool:** none required

The project should run on any platform with Python 3.9 or later.

## How to run

The entry point is `run.py` at the project root. It takes a single argument: the path to an input file.

```bash
python3 run.py path/to/program.in
```

For example, the sample test cases:

```bash
python3 run.py tests/cases/case1.in       # prints: alert
python3 run.py tests/cases/case2.in       # prints: alert\nfan_on
python3 run.py tests/cases/case3.in       # prints: (no output)
python3 run.py tests/cases/case6.in       # prints: fan_on + a conflict diagnostic
python3 run.py tests/cases/case7.in       # prints: (no output) + a redundancy diagnostic
python3 run.py tests/cases/case8.in       # prints: (no output) + an inactive-rule diagnostic
python3 run.py tests/cases/case_chain.in  # prints: b\nc\nd\ne
```

Exit code is `0` on success, `1` on a lex or parse error (a one-line diagnostic is written to `stderr` — no Python traceback is shown).

## How to run the test suite

A diff-based test runner is included. It invokes the CLI on every `tests/cases/*.in` file and compares stdout byte-for-byte with the matching `*.expected` file.

```bash
python3 tests/run_tests.py
```

It prints `PASS` / `FAIL` per case and a summary at the end. Exit code is `0` if all cases pass, `1` otherwise.

## Project layout

```
.
├── README.md
├── run.py                     # thin CLI wrapper
├── resources/
│   └── rules-language.pdf     # original project brief
├── rules/                     # implementation package
│   ├── __init__.py
│   ├── lexer.py               # hand-written lexer
│   ├── ast_nodes.py           # AST node dataclasses
│   ├── parser.py              # recursive-descent LL(1) parser
│   ├── interpreter.py         # fixed-point evaluator
│   ├── analyzer.py            # static analysis (conflicts, redundancies, inactive rules)
│   └── cli.py                 # main()
└── tests/
    ├── run_tests.py           # diff-based test runner
    └── cases/                 # input/expected pairs
        ├── case1.in / case1.expected     # §7.1 — single rule with comparison
        ├── case2.in / case2.expected     # §7.2 — chain (alert → fan_on)
        ├── case3.in / case3.expected     # §7.3 — no firing rules
        ├── case4.in / case4.expected     # §7.4 — AND of two comparisons
        ├── case5.in / case5.expected     # §7.5 — state only, no rules
        ├── case6.in / case6.expected     # §7.6 — conflict detection
        ├── case7.in / case7.expected     # §7.7 — redundancy detection
        ├── case8.in / case8.expected     # §7.8 — inactive-rule detection
        └── case_chain.in / case_chain.expected  # additional grading case from p.9
```

## Language reference

### Surface syntax

```
rule <id>:
    if <cond> then <action>

[more rules, separated by one or more blank lines]

State:
<id> = <integer>     # variable assignment
<id>                  # active fact
```

### Grammar (minimal, per §2.2 of the brief)

```
Program  → RuleList
RuleList → Rule RuleList | ε
Rule     → "rule" id ":" "if" Cond "then" Action
Cond     → Cond "AND" Cond | Atom
Atom     → id RelOp value | id
RelOp    → ">" | "<" | "="
Action   → id
```

This grammar is **left-recursive in `Cond`** and **not factored in `Atom`**, so it is not LL(1) as written. We use the equivalent LL(1) grammar internally:

```
Cond     → Atom CondTail
CondTail → "AND" Atom CondTail | ε
Atom     → id AtomTail
AtomTail → RelOp value | ε
```

### Constraints (per §2.3)

- Identifiers: `[a-z][a-z0-9_]*` (lowercase letter start; lowercase letters, digits, underscores).
- Integer literals: `[0-9]+` (base-10, non-negative).
- Keywords (`rule`, `if`, `then`, `AND`, `State`) are case-sensitive.
- Spaces, tabs, and extra blank lines are ignored.

### AST shape (per §2.4)

| Node | Fields |
| --- | --- |
| `Program` | `rules: list[Rule]` |
| `Rule` | `name: str`, `cond: Cond`, `action: Action` |
| `AndCond` | `left: Cond`, `right: Cond` |
| `Comparison` | `ident: str`, `op: str`, `value: int` |
| `Fact` | `ident: str` |
| `Action` | `ident: str` |

`AndCond` chains are built left-leaning by the parser, so `a AND b AND c` parses as `AndCond(AndCond(a, b), c)`.

### Evaluation (per §2.5)

- The environment is a pair of (a) a variable map `id → int` and (b) a set of active facts.
- A `Comparison(x, op, v)` is true if `x` is defined and the comparison holds. An undefined variable evaluates to `false` (the analyzer is responsible for flagging this).
- A `Fact(x)` is true if `x` is in the active fact set.
- An `AndCond(c1, c2)` is true if both subconditions hold.
- Execution is a **fixed point**: each iteration evaluates every rule against the same snapshot, collects the actions of applicable rules, and unions them into the fact set. The loop terminates when no new facts are added.
- Determinism: order-independent — the snapshot in each iteration is shared.

### Output (per §2.6)

- The output is the set of facts **activated by rule execution**, excluding initial facts present in the State block.
- Facts are printed one per line, sorted lexicographically, each at most once.
- If no facts are activated, the output is exactly `(no output)`.
- Static-analysis messages follow the execution output, one per line. The CLI prints `(no output)` first even when only analysis messages follow.

### Static analysis (per §2.6)

Three kinds of diagnostics are produced:

- **Conflict** — an action is produced by ≥2 rules belonging to ≥2 distinct condition groups.
  ```
  Action <id> generated by r1, r2, ...
  ```
  Suppressed when all producing rules are identical (already reported as redundant; see case 7).
- **Redundancy** — ≥2 rules with the same canonical condition and the same action. Conditions are compared modulo AND-commutativity, so `a AND b` and `b AND a` are detected.
  ```
  Redundant rules: r1, r2
  ```
- **Potentially inactive rule** — a rule whose comparison is falsified by the initial state, whose action is not consumed elsewhere, and which exists in a program containing at least one other rule whose comparisons are not falsified.
  ```
  Potentially inactive rule: <id>
  ```
  This heuristic matches case 8 of the brief exactly: r1 has a falsified comparison but its action `alert` feeds r2 (so it is not flagged); r3 has a falsified comparison and its action `cooling` is a leaf, while r2 (no comparison) is "live", so r3 is flagged.

## Notes on implementation choices

- **No external dependencies, no parser generator.** All parsing is hand-written recursive descent with one token of lookahead, as required by §6.
- **AST as frozen dataclasses.** Conditions are duck-typed: `AndCond`, `Comparison`, and `Fact` share no common base class; the interpreter and analyzer dispatch on `isinstance` checks.
- **Lexer collapses whitespace runs.** Multiple blank lines between rules collapse to a single `NEWLINE` token, which the parser treats as a soft separator.
- **Error handling.** `LexError` and `ParseError` carry source position and a clear message. The CLI catches them and exits with code `1` to `stderr`, never showing a Python traceback to the user.
