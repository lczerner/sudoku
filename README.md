# Sudoku PDF generator

Generates classic 9x9 sudoku puzzles and writes them to a printable A4 PDF,
with solution pages at the end. Needs only Python 3.10+, no extra packages.

```
./sudoku.py -d hard -n 8            # 8 hard puzzles, 4 per page -> sudoku.pdf
./sudoku.py -d easy -n 2 -p 1 -o easy.pdf --no-solutions
./sudoku.py --help
```

Every puzzle has exactly one solution. Difficulty is graded by the techniques
needed to solve it:

| Level  | Needs                                              |
|--------|----------------------------------------------------|
| easy   | naked/hidden singles only, about 38 givens          |
| medium | naked/hidden singles only, fewer givens (about 24-31) |
| hard   | locked candidates or naked pairs                   |
| expert | techniques beyond those                            |
