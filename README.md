# Sudoku PDF generator

Generates sudoku puzzles and writes them to a printable A4 PDF, optionally
with solution pages at the end. Needs only Python 3.10+, no extra packages.

```
./sudoku.py -d hard -n 8            # 8 hard puzzles -> sudoku.pdf
./sudoku.py -d easy -n 2 -p 1 -o easy.pdf --solutions
./sudoku.py -s 6 -n 6 -p 6          # 6x6 puzzles using numbers 1-6
./sudoku.py --help
```

Without `-p`, each page holds as many puzzles as fit with digits of at least
14 pt: 20 on 4x4, 12 on 6x6, 6 on 8x8 and 9x9. `-p` can ask for fewer, not more.

Every puzzle has exactly one solution. Difficulty is graded by the techniques
needed to solve it:

| Level  | Needs                                              |
|--------|----------------------------------------------------|
| easy   | naked/hidden singles only, about 47% of cells given (38 on 9x9) |
| medium | naked/hidden singles only, fewer givens (about 24-31 on 9x9) |
| hard   | locked candidates or naked pairs                   |
| expert | techniques beyond those                            |

`-s` sets how many numbers the puzzle uses, which is also the grid size:
4, 6, 8 or 9 (default), with boxes of 2x2, 2x3, 2x4 and 3x3. Sizes 5 and 7
have no rectangular boxes, so they are not offered. Hard and expert are only
available on 9x9; smaller grids rarely or never need more than singles.

## License

MIT, see [LICENSE](LICENSE).
