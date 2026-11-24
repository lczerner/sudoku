#!/usr/bin/env python3
"""Generate classic 9x9 sudoku puzzles and write them to a printable A4 PDF."""

import argparse
import random
import sys
from itertools import combinations

ALL = 0b1111111110  # candidate bits for digits 1-9

ROWS = [[r * 9 + c for c in range(9)] for r in range(9)]
COLS = [[r * 9 + c for r in range(9)] for c in range(9)]
BOXES = [[(br + r) * 9 + bc + c for r in range(3) for c in range(3)]
         for br in (0, 3, 6) for bc in (0, 3, 6)]
UNITS = ROWS + COLS + BOXES
PEERS = [sorted({p for u in UNITS if i in u for p in u} - {i}) for i in range(81)]
BOX_OF = [(i // 27) * 3 + (i % 9) // 3 for i in range(81)]
INTERSECTIONS = [(set(box), set(line), set(box) & set(line))
                 for box in BOXES for line in ROWS + COLS if set(box) & set(line)]

LEVELS = ("easy", "medium", "hard", "expert")
EASY_GIVENS = 38


def search(grid, limit, rng=None):
    """Backtracking solver. Returns (number of solutions up to limit, first solution)."""
    grid = grid[:]
    rows, cols, boxes = [0] * 9, [0] * 9, [0] * 9
    for i, v in enumerate(grid):
        if v:
            rows[i // 9] |= 1 << v
            cols[i % 9] |= 1 << v
            boxes[BOX_OF[i]] |= 1 << v
    empty = [i for i in range(81) if not grid[i]]
    first = []

    def rec():
        best, best_mask, best_n = -1, 0, 10
        for i in empty:
            if grid[i]:
                continue
            mask = ALL & ~(rows[i // 9] | cols[i % 9] | boxes[BOX_OF[i]])
            n = mask.bit_count()
            if n < best_n:
                best, best_mask, best_n = i, mask, n
                if n <= 1:
                    break
        if best < 0:
            if not first:
                first.append(grid[:])
            return 1
        if best_n == 0:
            return 0
        r, c, b = best // 9, best % 9, BOX_OF[best]
        digits = [d for d in range(1, 10) if best_mask >> d & 1]
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
    values = puzzle[:]
    cand = [0] * 81
    for i in range(81):
        if not values[i]:
            cand[i] = ALL
            for p in PEERS[i]:
                cand[i] &= ~(1 << values[p])

    def place(i, d):
        values[i] = d
        cand[i] = 0
        for p in PEERS[i]:
            cand[p] &= ~(1 << d)

    def eliminate(cells, bits):
        changed = False
        for i in cells:
            if cand[i] & bits:
                cand[i] &= ~bits
                changed = True
        return changed

    def singles():
        for i in range(81):
            if cand[i].bit_count() == 1:
                place(i, cand[i].bit_length() - 1)
                return True
        for unit in UNITS:
            for d in range(1, 10):
                cells = [i for i in unit if cand[i] >> d & 1]
                if len(cells) == 1:
                    place(cells[0], d)
                    return True
        return False

    def locked_candidates():
        for box, line, inter in INTERSECTIONS:
            for d in range(1, 10):
                in_box = {i for i in box if cand[i] >> d & 1}
                in_line = {i for i in line if cand[i] >> d & 1}
                if in_box and in_box <= inter and eliminate(in_line - inter, 1 << d):
                    return True
                if in_line and in_line <= inter and eliminate(in_box - inter, 1 << d):
                    return True
        return False

    def naked_pairs():
        for unit in UNITS:
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


def generate(level, rng):
    """Return (puzzle, solution) with a unique solution at the given difficulty.

    easy:   solvable with singles, about 38 givens
    medium: solvable with singles, as few givens as possible
    hard:   needs locked candidates or naked pairs
    expert: needs techniques beyond those
    """
    while True:
        _, solution = search([0] * 81, 1, rng)
        puzzle = solution[:]
        givens = 81
        # Remove cells in symmetric pairs (i, 80 - i); 40 is the centre cell.
        order = list(range(41))
        rng.shuffle(order)
        for i in order:
            if level == "easy" and givens <= EASY_GIVENS:
                break
            cells = {i, 80 - i}
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
    cell = size / 9
    thick = max(1.0, size * 0.006)
    for k in range(1, 9):
        width = thick if k % 3 == 0 else 0.5
        pdf.line(x + k * cell, y, x + k * cell, y + size, width)
        pdf.line(x, y + k * cell, x + size, y + k * cell, width)
    pdf.rect(x, y, size, size, thick)

    fs = cell * 0.6
    for i in range(81):
        digit = puzzle[i] or (solution[i] if solution else 0)
        if digit:
            r, c = divmod(i, 9)
            # Helvetica digits are 0.556 em wide and about 0.7 em tall.
            pdf.text(x + (c + 0.5) * cell - 0.278 * fs, y + (8.5 - r) * cell - 0.35 * fs,
                     str(digit), fs, bold=bool(puzzle[i]), gray=0 if puzzle[i] else 0.45)


def render(pdf, entries, cols, rows, margin=36, gap=24, label_size=11):
    """Lay out (label, puzzle, solution) entries, cols x rows per page."""
    per_page = cols * rows
    slot_w = (pdf.W - 2 * margin) / cols
    slot_h = (pdf.H - 2 * margin) / rows
    label_h = label_size * 1.8
    size = min(slot_w - gap, slot_h - gap - label_h)
    for n, (label, puzzle, solution) in enumerate(entries):
        if n % per_page == 0:
            pdf.add_page()
        col, row = n % cols, n % per_page // cols
        left = margin + (col + 0.5) * slot_w - size / 2
        top = pdf.H - margin - row * slot_h - (slot_h - size - label_h) / 2
        pdf.text(left, top - label_size, label, label_size, bold=True)
        draw_grid(pdf, left, top - label_h - size, size, puzzle, solution)


LAYOUTS = {1: (1, 1), 2: (1, 2), 4: (2, 2), 6: (2, 3)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-d", "--difficulty", choices=LEVELS, default="medium")
    ap.add_argument("-n", "--count", type=int, default=4, help="number of puzzles (default 4)")
    ap.add_argument("-p", "--per-page", type=int, choices=sorted(LAYOUTS), default=4,
                    help="puzzles per page (default 4)")
    ap.add_argument("-o", "--output", default="sudoku.pdf", help="output file (default sudoku.pdf)")
    ap.add_argument("--no-solutions", action="store_true", help="leave out the solution pages")
    ap.add_argument("--seed", type=int, help="random seed, for reproducible output")
    args = ap.parse_args()
    if args.count < 1:
        ap.error("--count must be at least 1")

    rng = random.Random(args.seed)
    games = []
    for n in range(args.count):
        print(f"Generating puzzle {n + 1}/{args.count}...", end="\r", file=sys.stderr)
        games.append(generate(args.difficulty, rng))
    print(file=sys.stderr)

    level = args.difficulty.capitalize()
    pdf = PDF()
    render(pdf, [(f"#{n}  {level}", p, None) for n, (p, _) in enumerate(games, 1)],
           *LAYOUTS[args.per_page])
    if not args.no_solutions:
        render(pdf, [(f"Solution #{n}", p, s) for n, (p, s) in enumerate(games, 1)],
               3, 4, label_size=9)
    pdf.save(args.output)
    print(f"Wrote {args.count} {args.difficulty} puzzle(s) to {args.output}")


if __name__ == "__main__":
    main()
