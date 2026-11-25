# SPDX-License-Identifier: MIT
# Copyright 2026 Lukáš Czerner <lukas@czerner.cz>
"""Tests that generated puzzles, and the ones printed in the PDF, have exactly
one solution. Run with: python3 -m unittest"""

import random
import re
import subprocess
import sys
import tempfile
import unittest
from math import floor
from pathlib import Path

import sudoku

SCRIPT = Path(__file__).with_name("sudoku.py")


def units(n):
    """Rows, columns and boxes of an n x n grid, built independently of sudoku.py."""
    bh, bw = sudoku.BOX_SHAPES[n]
    rows = [[(r, c) for c in range(n)] for r in range(n)]
    cols = [[(r, c) for r in range(n)] for c in range(n)]
    boxes = [[(br + r, bc + c) for r in range(bh) for c in range(bw)]
             for br in range(0, n, bh) for bc in range(0, n, bw)]
    return rows + cols + boxes


def is_valid_solution(puzzle, solution, n):
    """Every unit holds 1..n once and the solution keeps the puzzle's givens."""
    grid = {(i // n, i % n): v for i, v in enumerate(solution)}
    return (all(sorted(grid[cell] for cell in u) == list(range(1, n + 1)) for u in units(n))
            and all(p in (0, s) for p, s in zip(puzzle, solution)))


def count_solutions(puzzle, n, limit=2):
    """Plain backtracking solution counter, kept separate from sudoku.search()
    so the tests do not rely on the solver they check."""
    grid = {(i // n, i % n): v for i, v in enumerate(puzzle)}
    peers = {cell: {p for u in units(n) if cell in u for p in u} - {cell} for cell in grid}
    if any(v and v in {grid[p] for p in peers[cell]} for cell, v in grid.items()):
        return 0

    def options(cell):
        return set(range(1, n + 1)) - {grid[p] for p in peers[cell]}

    def rec():
        empty = [cell for cell in grid if not grid[cell]]
        if not empty:
            return 1
        cell = min(empty, key=lambda c: len(options(c)))
        found = 0
        for d in options(cell):
            grid[cell] = d
            found += rec()
            grid[cell] = 0
            if found >= limit:
                break
        return found

    return rec()


def read_pdf_grids(path, n):
    """Grids drawn in a PDF written by sudoku.PDF, in page order, as
    (givens, all digits, box borders): bold digits are givens, grey ones are
    filled in; box borders are the inner thick lines as (set of columns, set
    of rows) they precede, counted from the top-left corner."""
    data = Path(path).read_bytes().decode("latin-1")
    grids, lines = [], []
    for stream in re.findall(r"stream\n(.*?)\nendstream", data, re.S):
        for line in stream.splitlines():
            # draw_grid() draws the inner lines, then the outline, then the digits.
            if m := re.search(r"^([\d.]+) w ([\d.]+) ([\d.]+) m ([\d.]+) ([\d.]+) l S$", line):
                lines.append(tuple(map(float, m.groups())))
            elif m := re.search(r"^[\d.]+ w ([\d.]+) ([\d.]+) ([\d.]+) [\d.]+ re S$", line):
                x, y, size = map(float, m.groups())
                cell, top = size / n, y + size
                cols = {round((x1 - x) / cell) for w, x1, _, x2, _ in lines
                        if x1 == x2 and w > 0.5}
                rows = {round((top - y1) / cell) for w, _, y1, _, y2 in lines
                        if y1 == y2 and w > 0.5}
                grids.append((x, y, cell, [0] * (n * n), [0] * (n * n), (cols, rows)))
                lines = []
            elif m := re.search(r"/F(\d) [\d.]+ Tf ([\d.]+) ([\d.]+) Td \((\d+)\) Tj", line):
                x, y, cell, givens, digits, _ = grids[-1]
                r = n - 1 - floor((float(m[3]) - y) / cell)
                c = floor((float(m[2]) - x) / cell)
                assert 0 <= r < n and 0 <= c < n, "digit outside its grid"
                digits[r * n + c] = int(m[4])
                if m[1] == "2":
                    givens[r * n + c] = int(m[4])
    return [(givens, digits, borders) for *_, givens, digits, borders in grids]


def read_pdf_pages(path):
    """(number of grids, smallest digit font size) of each page of a PDF
    written by sudoku.PDF."""
    data = Path(path).read_bytes().decode("latin-1")
    return [(len(re.findall(r" re S$", stream, re.M)),
             min(map(float, re.findall(r"/F\d ([\d.]+) Tf [\d.]+ [\d.]+ Td \(\d+\) Tj", stream))))
            for stream in re.findall(r"stream\n(.*?)\nendstream", data, re.S)]


def levels(n):
    return sudoku.LEVELS if n == 9 else ("easy", "medium")


class GenerateTest(unittest.TestCase):
    def test_puzzles_have_one_valid_solution(self):
        rng = random.Random(1)
        for n in sudoku.BOX_SHAPES:
            for level in levels(n):
                for k in range(10):
                    with self.subTest(size=n, level=level, puzzle=k):
                        puzzle, solution = sudoku.generate(level, rng, n)
                        self.assertEqual(len(puzzle), n * n)
                        self.assertTrue(is_valid_solution(puzzle, solution, n))
                        self.assertEqual(count_solutions(puzzle, n), 1)
                        self.assertEqual(sudoku.search(puzzle, 2), (1, solution))

    def test_levels_match_techniques(self):
        rng = random.Random(2)
        for n in sudoku.BOX_SHAPES:
            for level in levels(n):
                for k in range(5):
                    with self.subTest(size=n, level=level, puzzle=k):
                        puzzle, _ = sudoku.generate(level, rng, n)
                        singles = sudoku.solve_logically(puzzle, advanced=False)
                        advanced = sudoku.solve_logically(puzzle, advanced=True)
                        expected = {"easy": singles, "medium": singles,
                                    "hard": advanced and not singles,
                                    "expert": not advanced}
                        self.assertTrue(expected[level])


class PDFTest(unittest.TestCase):
    """Generate PDFs and check the puzzles as printed, not just as generated."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name, "out.pdf")

    def run_sudoku(self, n, level, count, *args, check=True):
        return subprocess.run([sys.executable, SCRIPT, "-s", str(n), "-d", level,
                               "-n", str(count), "--seed", "3", "-o", self.out, *args],
                              check=check, capture_output=True)

    def check_pdf(self, n, level, count=6):
        self.run_sudoku(n, level, count, "--solutions")
        grids = read_pdf_grids(self.out, n)
        self.assertEqual(len(grids), 2 * count)
        bh, bw = sudoku.BOX_SHAPES[n]
        borders = ({k for k in range(1, n) if k % bw == 0},
                   {k for k in range(1, n) if k % bh == 0})
        for k, ((puzzle, shown, puzzle_borders), (givens, solution, solution_borders)) in \
                enumerate(zip(grids[:count], grids[count:]), 1):
            with self.subTest(puzzle=k):
                self.assertEqual(puzzle_borders, borders, "wrong box borders")
                self.assertEqual(solution_borders, borders, "wrong box borders")
                self.assertEqual(puzzle, shown, "puzzle page shows non-given digits")
                self.assertEqual(givens, puzzle, "solution page givens differ from puzzle")
                self.assertTrue(is_valid_solution(puzzle, solution, n))
                self.assertEqual(count_solutions(puzzle, n), 1)

    def test_printed_puzzles(self):
        for n in sudoku.BOX_SHAPES:
            for level in levels(n):
                with self.subTest(size=n, level=level):
                    self.check_pdf(n, level)

    def test_default_per_page(self):
        """Without --per-page, a page holds as many puzzles as fit with digits
        of at least MIN_FONT; asking for more per page is refused."""
        for n in sudoku.BOX_SHAPES:
            with self.subTest(size=n):
                most = sudoku.max_per_page(n)
                self.run_sudoku(n, "easy", most + 1)
                pages = read_pdf_pages(self.out)
                self.assertEqual([grids for grids, _ in pages], [most, 1])
                self.assertGreaterEqual(min(font for _, font in pages), sudoku.MIN_FONT)
                self.run_sudoku(n, "easy", most, "-p", str(most - 1))
                self.assertEqual([grids for grids, _ in read_pdf_pages(self.out)], [most - 1, 1])
                refused = self.run_sudoku(n, "easy", 1, "-p", str(most + 1), check=False)
                self.assertEqual(refused.returncode, 2)


if __name__ == "__main__":
    unittest.main()
