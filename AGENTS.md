# AGENTS.md

Command-line generator of sudoku puzzles (4x4, 6x6, 8x8 or the classic 9x9)
that writes them to a printable A4 PDF. Usage and difficulty levels are in [README.md](README.md).

## Layout

- `sudoku.py`: the whole program, in sections:
  - `BOX_SHAPES`, `geometry()`: supported sizes and the cached units and
    lookup tables of each; the functions below take the size from the length
    of the grid list.
  - `search()`: bitmask backtracking solver; counts solutions (up to a limit)
    and, with an `rng`, builds random full grids.
  - `solve_logically()`: human-style solver used to grade difficulty
    (naked/hidden singles; with `advanced`, also locked candidates and naked pairs).
  - `generate()`: makes a full grid, then removes cells in 180°-symmetric pairs
    while the puzzle stays solvable at the target level, and retries until the
    grading matches.
  - `PDF`: minimal hand-written PDF writer (lines, rectangles, Helvetica text).
  - `draw_grid()`, `render()`, `LAYOUTS`: page layout of puzzles and solutions.
  - `main()`: CLI.
- `test_sudoku.py`: unittest suite; checks that generated puzzles, and the
  puzzles as printed in a generated PDF, have exactly one valid solution and
  the right level.
- `.claude/agents/sudoku-reviewer.md`: the review subagent (see below).

## Constraints

- Standard library only, Python 3.10+. Don't add dependencies.
- Every puzzle must have exactly one solution, and its level must follow from
  the techniques in `solve_logically()`, not from the number of givens alone
  (except easy, which also stops at `EASY_FILL` of the cells given).
- Hard and expert are only offered for size 9 (`main()` refuses them for
  smaller sizes; `generate()` would retry forever on 4x4).
- PDF text uses the built-in Helvetica fonts with WinAnsi encoding, so strings
  must be Latin-1 encodable.
- MIT licensed ([LICENSE](LICENSE)). Every code file starts (after any
  shebang) with:

  ```
  # SPDX-License-Identifier: MIT
  # Copyright 2026 Lukáš Czerner <lukas@czerner.cz>
  ```

## Running

```
./sudoku.py -d hard -n 6 -o /tmp/test.pdf
```

Tests: `python3 -m unittest` (stdlib only, a few seconds). Further
verification steps live in the reviewer agent.

## Before every commit

1. Stage the changes.
2. Have the staged diff reviewed by an expert: run the `sudoku-reviewer`
   subagent on it (on a repository with no commits yet, on all staged files).
3. Fix the real problems it reports, re-run it if the fixes were non-trivial,
   then commit.

Do not commit without a review of the exact changes being committed.
