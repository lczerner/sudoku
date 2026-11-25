#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright 2026 Lukáš Czerner <lukas@czerner.cz>
"""Generate sudoku puzzles (9x9 by default) and write them to a printable A4 PDF."""

import argparse
import random
import sys
from functools import cache
from itertools import combinations
from math import isqrt
from types import SimpleNamespace

# Grid size (numbers per row) -> shape of a box as (rows, columns).
BOX_SHAPES = {4: (2, 2), 6: (2, 3), 8: (2, 4), 9: (3, 3)}

LEVELS = ("easy", "medium", "hard", "expert")
EASY_FILL = 0.47  # share of cells given in an easy puzzle (38 on 9x9)
MIN_FONT = 14  # smallest digit size on puzzle pages in points; cells of about 8 mm
DIGIT_SCALE = 0.6  # digit font size relative to the cell
MARGIN, GAP = 36, 24  # page margin and minimum space between grids, in points


@cache
def geometry(n):
    """Units and lookup tables of an n x n grid."""
    bh, bw = BOX_SHAPES[n]
    rows = [[r * n + c for c in range(n)] for r in range(n)]
    cols = [[r * n + c for r in range(n)] for c in range(n)]
    boxes = [[(br + r) * n + bc + c for r in range(bh) for c in range(bw)]
             for br in range(0, n, bh) for bc in range(0, n, bw)]
    units = rows + cols + boxes
    box_of = [0] * (n * n)
    for b, box in enumerate(boxes):
        for i in box:
            box_of[i] = b
    return SimpleNamespace(
        n=n, box_h=bh, box_w=bw, all=((1 << n) - 1) << 1, units=units, box_of=box_of,
        peers=[sorted({p for u in units if i in u for p in u} - {i}) for i in range(n * n)],
        intersections=[(set(box), set(line), set(box) & set(line))
                       for box in boxes for line in rows + cols if set(box) & set(line)])


def search(grid, limit, rng=None):
    """Backtracking solver. Returns (number of solutions up to limit, first solution)."""
    g = geometry(isqrt(len(grid)))
    n, box_of = g.n, g.box_of
    grid = grid[:]
    rows, cols, boxes = [0] * n, [0] * n, [0] * n
    for i, v in enumerate(grid):
        if v:
            rows[i // n] |= 1 << v
            cols[i % n] |= 1 << v
            boxes[box_of[i]] |= 1 << v
    empty = [i for i in range(n * n) if not grid[i]]
    first = []

    def rec():
        best, best_mask, best_n = -1, 0, n + 1
        for i in empty:
            if grid[i]:
                continue
            mask = g.all & ~(rows[i // n] | cols[i % n] | boxes[box_of[i]])
            count = mask.bit_count()
            if count < best_n:
                best, best_mask, best_n = i, mask, count
                if count <= 1:
                    break
        if best < 0:
            if not first:
                first.append(grid[:])
            return 1
        if best_n == 0:
            return 0
        r, c, b = best // n, best % n, box_of[best]
        digits = [d for d in range(1, n + 1) if best_mask >> d & 1]
        if rng:
            rng.shuffle(digits)
        found = 0
        for d in digits:
            bit = 1 << d
            grid[best] = d
            rows[r] |= bit
            cols[c] |= bit
            boxes[b] |= bit
            found += rec()
            grid[best] = 0
            rows[r] ^= bit
            cols[c] ^= bit
            boxes[b] ^= bit
            if found >= limit:
                break
        return found

    count = rec()
    return count, (first[0] if first else None)


def solve_logically(puzzle, advanced):
    """Solve like a human would: naked and hidden singles, plus locked
    candidates and naked pairs when advanced. Returns True if that is enough."""
    g = geometry(isqrt(len(puzzle)))
    digits = range(1, g.n + 1)
    values = puzzle[:]
    cand = [0] * len(values)
    for i in range(len(values)):
        if not values[i]:
            cand[i] = g.all
            for p in g.peers[i]:
                cand[i] &= ~(1 << values[p])

    def place(i, d):
        values[i] = d
        cand[i] = 0
        for p in g.peers[i]:
            cand[p] &= ~(1 << d)

    def eliminate(cells, bits):
        changed = False
        for i in cells:
            if cand[i] & bits:
                cand[i] &= ~bits
                changed = True
        return changed

    def singles():
        for i in range(len(values)):
            if cand[i].bit_count() == 1:
                place(i, cand[i].bit_length() - 1)
                return True
        for unit in g.units:
            for d in digits:
                cells = [i for i in unit if cand[i] >> d & 1]
                if len(cells) == 1:
                    place(cells[0], d)
                    return True
        return False

    def locked_candidates():
        for box, line, inter in g.intersections:
            for d in digits:
                in_box = {i for i in box if cand[i] >> d & 1}
                in_line = {i for i in line if cand[i] >> d & 1}
                if in_box and in_box <= inter and eliminate(in_line - inter, 1 << d):
                    return True
                if in_line and in_line <= inter and eliminate(in_box - inter, 1 << d):
                    return True
        return False

    def naked_pairs():
        for unit in g.units:
            pairs = [i for i in unit if cand[i].bit_count() == 2]
            for a, b in combinations(pairs, 2):
                if cand[a] == cand[b] and eliminate(
                        [i for i in unit if i not in (a, b)], cand[a]):
                    return True
        return False

    while 0 in values:
        if singles():
            continue
        if advanced and (locked_candidates() or naked_pairs()):
            continue
        return False
    return True


def generate(level, rng, size=9):
    """Return (puzzle, solution) of a size x size grid with a unique solution
    at the given difficulty.

    easy:   solvable with singles, EASY_FILL of the cells given
    medium: solvable with singles, as few givens as possible
    hard:   needs locked candidates or naked pairs
    expert: needs techniques beyond those
    """
    total = size * size
    while True:
        _, solution = search([0] * total, 1, rng)
        puzzle = solution[:]
        givens = total
        # Remove cells in symmetric pairs (i, last - i); on odd sizes the
        # middle index is the centre cell on its own.
        order = list(range((total + 1) // 2))
        rng.shuffle(order)
        for i in order:
            if level == "easy" and givens <= round(total * EASY_FILL):
                break
            cells = {i, total - 1 - i}
            trial = puzzle[:]
            for j in cells:
                trial[j] = 0
            if level in ("easy", "medium"):
                ok = solve_logically(trial, advanced=False)
            elif level == "hard":
                ok = solve_logically(trial, advanced=True)
            else:
                ok = search(trial, 2)[0] == 1
            if ok:
                puzzle = trial
                givens -= len(cells)
        if level == "hard" and solve_logically(puzzle, advanced=False):
            continue
        if level == "expert" and solve_logically(puzzle, advanced=True):
            continue
        return puzzle, solution


class PDF:
    """Minimal PDF writer: lines, rectangles and Helvetica text on A4 pages."""

    W, H = 595.28, 841.89

    def __init__(self):
        self.pages = []

    def add_page(self):
        self.pages.append([])

    def line(self, x1, y1, x2, y2, width):
        self.pages[-1].append(f"{width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    def rect(self, x, y, w, h, width):
        self.pages[-1].append(f"{width:.2f} w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")

    def text(self, x, y, s, size, bold=False, gray=0.0):
        s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        font = "F2" if bold else "F1"
        self.pages[-1].append(
            f"{gray:.2f} g BT /{font} {size:.2f} Tf {x:.2f} {y:.2f} Td ({s}) Tj ET")

    def save(self, path):
        font = "<< /Type /Font /Subtype /Type1 /BaseFont /{} /Encoding /WinAnsiEncoding >>"
        objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"",
                font.format("Helvetica").encode(), font.format("Helvetica-Bold").encode()]
        kids = []
        for ops in self.pages:
            stream = "\n".join(ops).encode("latin-1")
            objs.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream))
            objs.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.W} {self.H}] "
                         f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> "
                         f"/Contents {len(objs)} 0 R >>").encode())
            kids.append(f"{len(objs)} 0 R")
        objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>".encode()

        out = bytearray(b"%PDF-1.4\n")
        offsets = []
        for n, body in enumerate(objs, 1):
            offsets.append(len(out))
            out += b"%d 0 obj\n%s\nendobj\n" % (n, body)
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for off in offsets:
            out += b"%010d 00000 n \n" % off
        out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
            len(objs) + 1, xref)
        with open(path, "wb") as f:
            f.write(out)


def draw_grid(pdf, x, y, size, puzzle, solution=None):
    """Draw a grid with its bottom-left corner at (x, y). Givens are bold;
    with a solution, the remaining digits are filled in grey."""
    g = geometry(isqrt(len(puzzle)))
    n = g.n
    cell = size / n
    thick = max(1.0, size * 0.006)
    for k in range(1, n):
        vertical = thick if k % g.box_w == 0 else 0.5
        horizontal = thick if (n - k) % g.box_h == 0 else 0.5
        pdf.line(x + k * cell, y, x + k * cell, y + size, vertical)
        pdf.line(x, y + k * cell, x + size, y + k * cell, horizontal)
    pdf.rect(x, y, size, size, thick)

    fs = cell * DIGIT_SCALE
    for i in range(n * n):
        digit = puzzle[i] or (solution[i] if solution else 0)
        if digit:
            r, c = divmod(i, n)
            # Helvetica digits are 0.556 em wide and about 0.7 em tall.
            pdf.text(x + (c + 0.5) * cell - 0.278 * fs, y + (n - 0.5 - r) * cell - 0.35 * fs,
                     str(digit), fs, bold=bool(puzzle[i]), gray=0 if puzzle[i] else 0.45)


def grid_size(cols, rows, label_size=11):
    """Side of each grid when a page holds cols x rows of them."""
    return min((PDF.W - 2 * MARGIN) / cols - GAP,
               (PDF.H - 2 * MARGIN) / rows - GAP - label_size * 1.8)


def layout(per_page):
    """(cols, rows) that fits per_page grids on a page with the most room for each."""
    return max(((cols, -(-per_page // cols)) for cols in range(1, per_page + 1)),
               key=lambda cr: grid_size(*cr))


def max_per_page(n):
    """Most n x n puzzles that fit on a page with digits of at least MIN_FONT."""
    per_page = 1
    while grid_size(*layout(per_page + 1)) / n * DIGIT_SCALE >= MIN_FONT:
        per_page += 1
    return per_page


def render(pdf, entries, per_page, label_size=11):
    """Lay out (label, puzzle, solution) entries, per_page on each page."""
    cols, rows = layout(per_page)
    slot_w = (pdf.W - 2 * MARGIN) / cols
    slot_h = (pdf.H - 2 * MARGIN) / rows
    label_h = label_size * 1.8
    size = grid_size(cols, rows, label_size)
    for n, (label, puzzle, solution) in enumerate(entries):
        if n % per_page == 0:
            pdf.add_page()
        col, row = n % cols, n % per_page // cols
        left = MARGIN + (col + 0.5) * slot_w - size / 2
        top = pdf.H - MARGIN - row * slot_h - (slot_h - size - label_h) / 2
        pdf.text(left, top - label_size, label, label_size, bold=True)
        draw_grid(pdf, left, top - label_h - size, size, puzzle, solution)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-d", "--difficulty", choices=LEVELS, default="medium",
                    help="hard and expert need size 9 (default medium)")
    ap.add_argument("-s", "--size", type=int, choices=sorted(BOX_SHAPES), default=9,
                    help="numbers per row, column and box (default 9)")
    ap.add_argument("-n", "--count", type=int, default=4, help="number of puzzles (default 4)")
    ap.add_argument("-p", "--per-page", type=int,
                    help=f"puzzles per page (default: as many as fit with digits of "
                         f"at least {MIN_FONT} pt)")
    ap.add_argument("-o", "--output", default="sudoku.pdf", help="output file (default sudoku.pdf)")
    ap.add_argument("--solutions", action="store_true", help="add solution pages at the end")
    ap.add_argument("--seed", type=int, help="random seed, for reproducible output")
    args = ap.parse_args()
    if args.count < 1:
        ap.error("--count must be at least 1")
    if args.size < 9 and args.difficulty in ("hard", "expert"):
        ap.error(f"{args.difficulty} puzzles need --size 9; smaller grids are easy or medium")
    most = max_per_page(args.size)
    if args.per_page is None:
        args.per_page = most
    elif not 1 <= args.per_page <= most:
        ap.error(f"--per-page must be 1 to {most} for --size {args.size}, "
                 f"so that digits stay at least {MIN_FONT} pt")

    rng = random.Random(args.seed)
    games = []
    for n in range(args.count):
        print(f"Generating puzzle {n + 1}/{args.count}...", end="\r", file=sys.stderr)
        games.append(generate(args.difficulty, rng, args.size))
    print(file=sys.stderr)

    level = args.difficulty.capitalize()
    pdf = PDF()
    render(pdf, [(f"#{n}  {level}", p, None) for n, (p, _) in enumerate(games, 1)],
           args.per_page)
    if args.solutions:
        render(pdf, [(f"Solution #{n}", p, s) for n, (p, s) in enumerate(games, 1)],
               12, label_size=9)
    pdf.save(args.output)
    print(f"Wrote {args.count} {args.difficulty} puzzle(s) to {args.output}")


if __name__ == "__main__":
    main()
