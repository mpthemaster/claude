"""A freeform crossword builder, and a medium-difficulty Twin Peaks puzzle made with it.

Entries come from a text file, one per line, as ``ANSWER | clue``. The builder
places as many entries as it can in a grid where every answer crosses at least
one other and no two letters touch by accident, numbers the result the usual
way, and renders it as SVG (puzzle and solution) or plain text.

Usage:
    python projects/crossword/crossword.py --out-dir projects/crossword/out
    python projects/crossword/crossword.py --words my-words.txt --seed 3 --text
"""

from __future__ import annotations

import argparse
import random
import re
import sys
from dataclasses import dataclass, replace
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_WORDS = HERE / "twin_peaks.txt"
DEFAULT_TITLE = "Twin Peaks"
DEFAULT_TRIES = 200
DEFAULT_MAX_SIZE = 23

Cell = tuple[int, int]


# ---------------------------------------------------------------- entries


@dataclass(frozen=True)
class Entry:
    """One answer and its clue. ``answer`` keeps its spaces and hyphens so the
    enumeration after the clue can show them; the grid holds ``letters``."""

    answer: str
    clue: str

    @property
    def letters(self) -> str:
        return letters_of(self.answer)

    @property
    def enumeration(self) -> str:
        """``(3,4)`` for LOG LADY, ``(3-5)`` for ONE-ARMED, ``(6)`` for COOPER."""
        out = []
        for token in re.findall(r"[A-Za-z']+|[ -]", self.answer):
            if token == " ":
                out.append(",")
            elif token == "-":
                out.append("-")
            else:
                out.append(str(len(letters_of(token))))
        return "(" + "".join(out) + ")"


def letters_of(answer: str) -> str:
    return re.sub(r"[^A-Z]", "", answer.upper())


def parse_entries(text: str) -> list[Entry]:
    """Read ``ANSWER | clue`` lines. Blank lines and ``#`` comments are skipped."""
    entries: list[Entry] = []
    seen: set[str] = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            raise ValueError(f"line {lineno}: expected 'ANSWER | clue'")
        answer, clue = (part.strip() for part in line.split("|", 1))
        if not re.fullmatch(r"[A-Za-z' -]+", answer):
            raise ValueError(f"line {lineno}: answer may only contain letters, spaces and hyphens")
        letters = letters_of(answer)
        if len(letters) < 2:
            raise ValueError(f"line {lineno}: an answer needs at least two letters")
        if letters in seen:
            raise ValueError(f"line {lineno}: {letters} appears twice")
        if not clue:
            raise ValueError(f"line {lineno}: missing clue")
        seen.add(letters)
        entries.append(Entry(answer, clue))
    return entries


# ---------------------------------------------------------------- placing


@dataclass(frozen=True)
class Placement:
    entry: Entry
    row: int
    col: int
    across: bool
    number: int = 0

    @property
    def cells(self) -> list[Cell]:
        n = len(self.entry.letters)
        if self.across:
            return [(self.row, self.col + i) for i in range(n)]
        return [(self.row + i, self.col) for i in range(n)]


def fit(cells: dict[Cell, str], word: str, row: int, col: int, across: bool) -> int | None:
    """How many existing letters ``word`` would cross if placed here, or None
    if it can't go here.

    A placement is refused when a letter disagrees with one already in the
    grid, when the cell before the first letter or after the last one is taken
    (the word would run into another), or when a newly written letter would
    touch a letter beside it (two words would read as one the solver never
    asked for). A word lying entirely on existing letters is refused too.
    """
    dr, dc = (0, 1) if across else (1, 0)
    n = len(word)
    if (row - dr, col - dc) in cells or (row + dr * n, col + dc * n) in cells:
        return None
    crossings = 0
    for i, letter in enumerate(word):
        r, c = row + dr * i, col + dc * i
        existing = cells.get((r, c))
        if existing is not None:
            if existing != letter:
                return None
            crossings += 1
        elif (r + dc, c + dr) in cells or (r - dc, c - dr) in cells:
            return None
    if crossings == n:
        return None
    return crossings


def bounds(cells: dict[Cell, str]) -> tuple[int, int, int, int]:
    """(min_row, min_col, max_row, max_col) of the letters placed so far."""
    rows = [r for r, _ in cells]
    cols = [c for _, c in cells]
    return min(rows), min(cols), max(rows), max(cols)


@dataclass
class Puzzle:
    placements: list[Placement]
    unplaced: list[Entry]
    rows: int
    cols: int

    @property
    def cells(self) -> dict[Cell, str]:
        grid: dict[Cell, str] = {}
        for p in self.placements:
            for cell, letter in zip(p.cells, p.entry.letters, strict=True):
                grid[cell] = letter
        return grid

    @property
    def crossings(self) -> int:
        """Cells where an across and a down answer share a letter."""
        counts: dict[Cell, int] = {}
        for p in self.placements:
            for cell in p.cells:
                counts[cell] = counts.get(cell, 0) + 1
        return sum(1 for n in counts.values() if n > 1)

    @property
    def across(self) -> list[Placement]:
        return [p for p in self.placements if p.across]

    @property
    def down(self) -> list[Placement]:
        return [p for p in self.placements if not p.across]

    def summary(self) -> str:
        letters = len(self.cells)
        checked = self.crossings
        return (
            f"{self.rows}x{self.cols}: {len(self.placements)} of "
            f"{len(self.placements) + len(self.unplaced)} answers placed, "
            f"{letters} letters, {checked} crossings ({100 * checked / max(letters, 1):.0f}%"
            f" of cells checked)"
        )


def build(entries: list[Entry], seed: int = 0, max_size: int = DEFAULT_MAX_SIZE) -> Puzzle:
    """Place entries greedily, roughly longest first (the seed jitters the
    order, since a long answer placed late rarely fits), each at the
    crossing-richest spot that keeps the grid compact. Entries that don't
    fit are retried after the others, then given up."""
    rng = random.Random(seed)
    queue = sorted(entries, key=lambda e: -(len(e.letters) + rng.uniform(-2, 2)))

    cells: dict[Cell, str] = {}
    index: dict[str, list[Cell]] = {}
    placed: list[Placement] = []

    def commit(entry: Entry, row: int, col: int, across: bool) -> None:
        p = Placement(entry, row, col, across)
        for cell, letter in zip(p.cells, entry.letters, strict=True):
            if cell not in cells:
                cells[cell] = letter
                index.setdefault(letter, []).append(cell)
        placed.append(p)

    def best_spot(entry: Entry) -> tuple[int, int, bool] | None:
        word = entry.letters
        if not cells:
            return (0, 0, True) if len(word) <= max_size else None
        min_r, min_c, max_r, max_c = bounds(cells)
        old_h, old_w = max_r - min_r + 1, max_c - min_c + 1
        best: tuple[float, int, int, bool] | None = None
        seen: set[tuple[int, int, bool]] = set()
        for i, letter in enumerate(word):
            for r, c in index.get(letter, ()):
                for across in (True, False):
                    row, col = (r, c - i) if across else (r - i, c)
                    if (row, col, across) in seen:
                        continue
                    seen.add((row, col, across))
                    crossings = fit(cells, word, row, col, across)
                    if not crossings:
                        continue
                    if across:
                        lo_r, hi_r, lo_c, hi_c = row, row, col, col + len(word) - 1
                    else:
                        lo_r, hi_r, lo_c, hi_c = row, row + len(word) - 1, col, col
                    new_h = max(max_r, hi_r) - min(min_r, lo_r) + 1
                    new_w = max(max_c, hi_c) - min(min_c, lo_c) + 1
                    if new_h > max_size or new_w > max_size:
                        continue
                    growth = (new_h - old_h) + (new_w - old_w)
                    score = 10 * crossings - 3 * growth + rng.random()
                    if best is None or score > best[0]:
                        best = (score, row, col, across)
        return None if best is None else best[1:]

    for _ in range(3):
        leftover: list[Entry] = []
        for entry in queue:
            spot = best_spot(entry)
            if spot is None:
                leftover.append(entry)
            else:
                commit(entry, *spot)
        queue = leftover
        if not queue:
            break

    return finish(placed, queue)


def finish(placed: list[Placement], unplaced: list[Entry]) -> Puzzle:
    """Shift the grid to start at (0, 0) and number the answers: row by row,
    left to right, one number per starting cell, shared by an across and a
    down answer that start in the same cell."""
    if not placed:
        return Puzzle([], list(unplaced), 0, 0)
    cells = {c for p in placed for c in p.cells}
    min_r = min(r for r, _ in cells)
    min_c = min(c for _, c in cells)
    shifted = [replace(p, row=p.row - min_r, col=p.col - min_c) for p in placed]
    starts = sorted({(p.row, p.col) for p in shifted})
    number_of = {cell: i + 1 for i, cell in enumerate(starts)}
    numbered = sorted(
        (replace(p, number=number_of[(p.row, p.col)]) for p in shifted),
        key=lambda p: (p.number, not p.across),
    )
    rows = max(r for r, _ in cells) - min_r + 1
    cols = max(c for _, c in cells) - min_c + 1
    return Puzzle(numbered, list(unplaced), rows, cols)


def best_build(
    entries: list[Entry], tries: int = DEFAULT_TRIES, max_size: int = DEFAULT_MAX_SIZE
) -> tuple[Puzzle, int]:
    """Build with seeds 0 to tries-1 and keep the best: most letters placed
    (so a long answer counts for more than a short one), then the most
    crossings, then the smallest grid. Returns (puzzle, seed)."""
    best: tuple[tuple[int, int, int], Puzzle, int] | None = None
    for seed in range(tries):
        puzzle = build(entries, seed, max_size)
        letters = sum(len(p.entry.letters) for p in puzzle.placements)
        key = (letters, puzzle.crossings, -puzzle.rows * puzzle.cols)
        if best is None or key > best[0]:
            best = (key, puzzle, seed)
    assert best is not None
    return best[1], best[2]


def runs(cells: dict[Cell, str]) -> list[tuple[Cell, bool, str]]:
    """Every maximal horizontal or vertical run of two or more letters, as
    (start cell, across, word). In a valid puzzle these are exactly the
    placed answers, which is what the tests check."""
    found: list[tuple[Cell, bool, str]] = []
    for across in (True, False):
        dr, dc = (0, 1) if across else (1, 0)
        for r, c in sorted(cells):
            if (r - dr, c - dc) in cells:
                continue
            word = ""
            rr, cc = r, c
            while (rr, cc) in cells:
                word += cells[rr, cc]
                rr, cc = rr + dr, cc + dc
            if len(word) >= 2:
                found.append(((r, c), across, word))
    return found


# ---------------------------------------------------------------- rendering

CELL = 28
MARGIN = 24
NUMBER_FONT = 8
LETTER_FONT = 16
CLUE_FONT = 12.5
LINE = 16
COLUMN_GAP = 28
MIN_INNER_WIDTH = 620
FONT = "Helvetica, Arial, sans-serif"


def wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap to at most ``width`` characters per line; a single
    word longer than that gets a line of its own."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def clue_line(p: Placement) -> str:
    return f"{p.number}. {p.entry.clue} {p.entry.enumeration}"


def render_svg(
    puzzle: Puzzle, title: str = DEFAULT_TITLE, *, solution: bool = False, clues: bool = True
) -> str:
    """The puzzle as one printable page: title, grid, and the clues in two
    columns. With ``solution=True`` the letters are filled in."""
    cells = puzzle.cells
    grid_w, grid_h = puzzle.cols * CELL, puzzle.rows * CELL
    inner_w = max(grid_w, MIN_INNER_WIDTH if clues else 0)
    width = inner_w + 2 * MARGIN
    grid_x = MARGIN + (inner_w - grid_w) / 2
    head_h = 52
    grid_y = MARGIN + head_h
    parts: list[str] = []
    subtitle = (
        "Solution"
        if solution
        else "The numbers in brackets give the length of each answer; a comma marks a new word"
    )

    parts.append(
        f'<text x="{MARGIN}" y="{MARGIN + 22}" font-family="{FONT}" font-size="24" '
        f'font-weight="bold" fill="#111">{escape(title)}</text>'
    )
    parts.append(
        f'<text x="{MARGIN}" y="{MARGIN + 42}" font-family="{FONT}" font-size="12" '
        f'fill="#555">{escape(subtitle)}</text>'
    )

    numbers = {(p.row, p.col): p.number for p in puzzle.placements}
    for (r, c), letter in sorted(cells.items()):
        x, y = grid_x + c * CELL, grid_y + r * CELL
        parts.append(
            f'<rect x="{x:g}" y="{y:g}" width="{CELL}" height="{CELL}" '
            'fill="#fff" stroke="#222" stroke-width="1.2"/>'
        )
        if (r, c) in numbers:
            parts.append(
                f'<text x="{x + 2.5:g}" y="{y + NUMBER_FONT + 1:g}" font-family="{FONT}" '
                f'font-size="{NUMBER_FONT}" fill="#333">{numbers[r, c]}</text>'
            )
        if solution:
            parts.append(
                f'<text x="{x + CELL / 2:g}" y="{y + CELL - 6:g}" font-family="{FONT}" '
                f'font-size="{LETTER_FONT}" text-anchor="middle" fill="#111">{letter}</text>'
            )

    y_end = grid_y + grid_h + MARGIN
    if clues:
        column_w = (inner_w - COLUMN_GAP) / 2
        chars = int(column_w / (CLUE_FONT * 0.55))
        y_end = grid_y + grid_h + 12
        bottoms = []
        for heading, group, x in (
            ("Across", puzzle.across, MARGIN),
            ("Down", puzzle.down, MARGIN + column_w + COLUMN_GAP),
        ):
            y = y_end + 20
            parts.append(
                f'<text x="{x:g}" y="{y:g}" font-family="{FONT}" font-size="{CLUE_FONT}" '
                f'font-weight="bold" fill="#111">{heading}</text>'
            )
            y += LINE * 1.4
            for p in group:
                lines = wrap(clue_line(p), chars)
                spans = "".join(
                    f'<tspan x="{x:g}" dy="{0 if i == 0 else LINE}">{escape(line)}</tspan>'
                    for i, line in enumerate(lines)
                )
                parts.append(
                    f'<text x="{x:g}" y="{y:g}" font-family="{FONT}" font-size="{CLUE_FONT}" '
                    f'fill="#111">{spans}</text>'
                )
                y += LINE * len(lines) + 4
            bottoms.append(y)
        y_end = max(bottoms) + MARGIN

    height = round(y_end)
    body = "\n".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height}" '
        f'viewBox="0 0 {width:g} {height}">\n'
        f'<rect width="100%" height="100%" fill="#fff"/>\n{body}\n</svg>\n'
    )


def render_text(puzzle: Puzzle, *, solution: bool = False) -> str:
    """The grid as text (letters, or ``#`` for a blank cell to fill, ``.`` for
    no cell) followed by the clues."""
    cells = puzzle.cells
    lines = []
    for r in range(puzzle.rows):
        row = ""
        for c in range(puzzle.cols):
            letter = cells.get((r, c))
            row += "." if letter is None else (letter if solution else "#")
        lines.append(row)
    lines.append("")
    for heading, group in (("Across", puzzle.across), ("Down", puzzle.down)):
        lines.append(heading)
        for p in group:
            suffix = f"  [{p.entry.letters}]" if solution else ""
            lines.append(f"  {clue_line(p)}{suffix}")
        lines.append("")
    return "\n".join(lines)


def render_markdown(puzzle: Puzzle) -> str:
    """The clues as a Markdown list, for a README."""
    lines = []
    for heading, group in (("Across", puzzle.across), ("Down", puzzle.down)):
        lines.append(f"**{heading}**")
        lines.append("")
        for p in group:
            lines.append(f"- **{p.number}.** {p.entry.clue} {p.entry.enumeration}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------- command line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a freeform crossword from a word list.")
    parser.add_argument("--words", type=Path, default=DEFAULT_WORDS, help="ANSWER | clue lines")
    parser.add_argument("--title", default=None, help="title on the page (default: file name)")
    parser.add_argument("--seed", type=int, default=None, help="one seed instead of the search")
    parser.add_argument("--tries", type=int, default=DEFAULT_TRIES, help="seeds to search")
    parser.add_argument("--max-size", type=int, default=DEFAULT_MAX_SIZE, help="grid side limit")
    parser.add_argument("--out-dir", type=Path, help="write <stem>.svg and <stem>-solution.svg")
    parser.add_argument("--text", action="store_true", help="print the puzzle as text")
    parser.add_argument("--solution", action="store_true", help="fill the letters in (--text)")
    parser.add_argument("--markdown", action="store_true", help="print the clues as Markdown")
    args = parser.parse_args(argv)
    if args.tries < 1 or args.max_size < 2:
        parser.error("--tries must be at least 1 and --max-size at least 2")

    entries = parse_entries(args.words.read_text(encoding="utf-8"))
    if args.seed is None:
        puzzle, seed = best_build(entries, args.tries, args.max_size)
    else:
        puzzle, seed = build(entries, args.seed, args.max_size), args.seed
    stem = args.words.stem.replace("_", "-")
    title = args.title or (DEFAULT_TITLE if args.words.resolve() == DEFAULT_WORDS else stem)

    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        (args.out_dir / f"{stem}.svg").write_text(render_svg(puzzle, title), encoding="utf-8")
        (args.out_dir / f"{stem}-solution.svg").write_text(
            render_svg(puzzle, title, solution=True, clues=False), encoding="utf-8"
        )
    if args.text:
        print(render_text(puzzle, solution=args.solution))
    if args.markdown:
        print(render_markdown(puzzle))
    print(f"seed {seed}, {puzzle.summary()}", file=sys.stderr)
    for entry in puzzle.unplaced:
        print(f"  not placed: {entry.answer}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
