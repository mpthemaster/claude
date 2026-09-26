"""The 256 elementary cellular automata on one poster, grouped by behaviour.

An elementary cellular automaton is a ring of cells, each 0 or 1. At every
step each cell looks at itself and its two neighbours and takes the value the
rule assigns to that three-cell neighbourhood. There are 2**8 = 256 rules,
numbered the way Wolfram numbers them: bit k of the rule number is the new
value for the neighbourhood whose cells (left, centre, right) spell k in
binary, so rule 30 = 0b00011110 sends 001, 010, 011 and 100 to 1.

This module runs every rule from a single black cell and from a random row,
classifies each rule by what its random runs settle into (uniform, periodic,
complex or chaotic), and lays all 256 out on one SVG poster grouped by class.

A row is a Python int with the leftmost cell in the most significant bit, so
one step is a handful of bit operations on the whole row at once.

Usage:
    python eca.py --out out/poster.svg      # the poster, with a summary on stderr
    python eca.py --rule 30 --steps 16      # one rule from a single cell, as text
    python eca.py --table                   # every rule's class and measures
"""

from __future__ import annotations

import argparse
import functools
import math
import random
import struct
import sys
import zlib
from base64 import b64encode
from dataclasses import dataclass
from pathlib import Path

# --- the classification experiment --------------------------------------------
#
# The ring is prime and 2 is a primitive root modulo it, so the additive rules
# (90, 150, 60, 105) have astronomically long periods on it. On a ring of 64
# cells rule 90 dies out completely after 64 steps, and on a ring of 63 it
# repeats every 63 steps; the README says why.
RING = 211
BUDGET = 4000  # steps a random run gets to fall into an exact cycle; see the README
TAIL = 256  # rows measured at the end of a run that never settled
SEEDS = (1, 2, 3, 4, 5)  # random rows per rule; the median verdict wins
STRUCTURE_THRESHOLD = 0.2  # bits per cell saved beyond what the density explains

KINDS = ("uniform", "periodic", "complex", "chaotic")
DESCRIPTIONS = {
    "uniform": "every random start ends all black or all white",
    "periodic": f"every random start falls into an exact cycle within {BUDGET} steps",
    "complex": f"no cycle in {BUDGET} steps, but the tail compresses well beyond its density",
    "chaotic": f"no cycle in {BUDGET} steps, and the tail compresses no better than a biased coin",
}

# --- the automaton --------------------------------------------------------------


def step(row: int, rule: int, width: int) -> int:
    """Advance one row of `width` cells by one step of `rule` on a ring."""
    mask = (1 << width) - 1
    # The leftmost cell is the most significant bit, so a cell's left
    # neighbour sits one bit up and its right neighbour one bit down.
    left = (row >> 1) | ((row & 1) << (width - 1))
    right = ((row << 1) | (row >> (width - 1))) & mask
    new = 0
    for k in range(8):
        if rule >> k & 1:
            has_l, has_c, has_r = k >> 2 & 1, k >> 1 & 1, k & 1
            new |= (
                (left if has_l else ~left) & (row if has_c else ~row) & (right if has_r else ~right)
            )
    return new & mask


def run(rule: int, row: int, steps: int, width: int = RING) -> list[int]:
    """The initial row followed by `steps` successors."""
    rows = [row]
    for _ in range(steps):
        row = step(row, rule, width)
        rows.append(row)
    return rows


def single_cell(width: int = RING) -> int:
    """One black cell in the middle of a white row."""
    return 1 << (width - 1 - width // 2)


def random_row(seed: int, width: int = RING) -> int:
    return random.Random(seed).getrandbits(width)


def to_bits(row: int, width: int) -> list[int]:
    return [int(ch) for ch in f"{row:0{width}b}"]


def from_bits(bits: list[int]) -> int:
    return int("".join(str(b) for b in bits), 2) if bits else 0


def crop(row: int, width: int, window: int) -> int:
    """The middle `window` cells of a row, as a row of that width."""
    offset = (width - window) // 2
    return (row >> (width - offset - window)) & ((1 << window) - 1)


def render_text(rows: list[int], width: int, ink: str = "#", paper: str = ".") -> str:
    return "\n".join(f"{row:0{width}b}".replace("1", ink).replace("0", paper) for row in rows)


# --- symmetries ----------------------------------------------------------------
#
# Swapping left and right, or swapping black and white, turns one rule into
# another with the same behaviour. That folds the 256 rules into 88 classes.


def mirror(rule: int) -> int:
    """The rule that does the same thing with left and right swapped."""
    out = 0
    for k in range(8):
        has_l, has_c, has_r = k >> 2 & 1, k >> 1 & 1, k & 1
        out |= (rule >> k & 1) << (has_r << 2 | has_c << 1 | has_l)
    return out


def complement(rule: int) -> int:
    """The rule that does the same thing with black and white swapped."""
    out = 0
    for k in range(8):
        out |= (1 - (rule >> (7 - k) & 1)) << k
    return out


def orbit(rule: int) -> tuple[int, ...]:
    """Every rule equivalent to this one, smallest first."""
    return tuple(sorted({rule, mirror(rule), complement(rule), mirror(complement(rule))}))


def representative(rule: int) -> int:
    return orbit(rule)[0]


def equivalence_classes() -> list[tuple[int, ...]]:
    return sorted({orbit(rule) for rule in range(256)})


def mirror_row(row: int, width: int) -> int:
    return int(f"{row:0{width}b}"[::-1], 2)


def complement_row(row: int, width: int) -> int:
    return row ^ ((1 << width) - 1)


def transform_from_representative(rule: int) -> tuple[bool, bool]:
    """(flip, invert) that carries the representative's runs onto this rule's.

    Running `rule` from a flipped and/or inverted row gives exactly the
    flipped and/or inverted run of its representative.
    """
    rep = representative(rule)
    for flip, invert in ((False, False), (True, False), (False, True), (True, True)):
        candidate = rep
        if flip:
            candidate = mirror(candidate)
        if invert:
            candidate = complement(candidate)
        if candidate == rule:
            return flip, invert
    raise AssertionError("unreachable: a rule is always in its own orbit")


def transform_row(row: int, width: int, flip: bool, invert: bool) -> int:
    if flip:
        row = mirror_row(row, width)
    if invert:
        row = complement_row(row, width)
    return row


# --- measures ------------------------------------------------------------------


def bits_per_cell(rows: list[int], width: int) -> float:
    """How many bits zlib needs per cell to store these rows.

    The rows are written out one character per cell before compressing, so a
    repeat that is shifted by a few cells is still a byte-aligned repeat and
    zlib can find it. Random cells cost a little over one bit each.
    """
    text = "".join(f"{row:0{width}b}" for row in rows).encode()
    return 8 * len(zlib.compress(text)) / len(text)


def binary_entropy(p: float) -> float:
    """Bits per cell that a biased coin with this density would cost."""
    if p <= 0 or p >= 1:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


@dataclass(frozen=True)
class Measure:
    """What one random run of a rule did."""

    rule: int
    seed: int
    homogeneous: bool  # the last row is all black or all white
    transient: int | None  # steps before the run entered its cycle; None if it never did
    period: int | None  # exact length of that cycle, None if there was none
    density: float  # fraction of black cells in the tail
    bits_per_cell: float  # zlib cost of the tail

    @property
    def structure(self) -> float:
        """Bits per cell saved beyond what a coin of the same bias would cost."""
        return binary_entropy(self.density) - self.bits_per_cell

    @property
    def kind(self) -> str:
        if self.homogeneous:
            return "uniform"
        if self.transient is not None:
            return "periodic"
        if self.structure < STRUCTURE_THRESHOLD:
            return "chaotic"
        return "complex"


def settle(rule: int, row: int, budget: int, width: int = RING) -> tuple[list[int], int | None]:
    """Run until a row repeats exactly, or for `budget` steps if none does.

    Returns the rows, ending with the first repeated row, and the step at
    which that row first appeared: the length of the transient before the
    cycle. The transient is None if nothing repeated within the budget.
    """
    rows = [row]
    seen = {row: 0}
    for t in range(1, budget + 1):
        row = step(row, rule, width)
        rows.append(row)
        if row in seen:
            return rows, seen[row]
        seen[row] = t
    return rows, None


def measure(
    rule: int, seed: int, width: int = RING, budget: int = BUDGET, tail: int = TAIL
) -> Measure:
    rows, transient = settle(rule, random_row(seed, width), budget, width)
    last = rows[-1]
    homogeneous = last in (0, (1 << width) - 1)
    period = len(rows) - 1 - transient if transient is not None else None
    end = rows[-tail:]
    density = sum(row.bit_count() for row in end) / (len(end) * width)
    return Measure(rule, seed, homogeneous, transient, period, density, bits_per_cell(end, width))


def verdict(measures: list[Measure]) -> str:
    """The median kind across seeds, on the scale uniform < periodic < complex < chaotic."""
    ranks = sorted(KINDS.index(m.kind) for m in measures)
    return KINDS[ranks[len(ranks) // 2]]


@functools.cache
def classify_all(seeds: tuple[int, ...] = SEEDS) -> dict[int, str]:
    """Class of every rule. Equivalent rules share a class by construction:

    the representative of each of the 88 classes is measured from each seed
    and its verdict is inherited by the whole class.
    """
    classes: dict[int, str] = {}
    for members in equivalence_classes():
        kind = verdict([measure(members[0], seed) for seed in seeds])
        for rule in members:
            classes[rule] = kind
    return classes


# --- the poster ----------------------------------------------------------------


def png(rows: list[int], width: int, ink: str = "#1b1b1f", paper: str = "#ffffff") -> bytes:
    """A 1-bit paletted PNG of the rows; cell 1 is drawn in `ink`."""
    stride = (width + 7) // 8
    raw = bytearray()
    for row in rows:
        raw.append(0)  # filter type: none
        raw += (row << (stride * 8 - width)).to_bytes(stride, "big")

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    def rgb(color: str) -> bytes:
        return bytes.fromhex(color.lstrip("#"))

    header = struct.pack(">IIBBBBB", width, len(rows), 1, 3, 0, 0, 0)  # 1 bit, palette
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", header),
            chunk(b"PLTE", rgb(paper) + rgb(ink)),
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)),
            chunk(b"IEND", b""),
        ]
    )


def image_element(rows: list[int], width: int, x: float, y: float) -> str:
    data = b64encode(png(rows, width)).decode()
    return (
        f'<image x="{x:g}" y="{y:g}" width="{width}" height="{len(rows)}" '
        f'image-rendering="optimizeSpeed" href="data:image/png;base64,{data}"/>'
    )


@dataclass(frozen=True)
class Layout:
    window: int = 81  # cells of the ring shown in each thumbnail
    random_rows: int = 48  # steps shown of the random run
    columns: int = 16
    gap: int = 10  # between thumbnails
    margin: int = 24
    label_height: int = 14
    heading_height: int = 44

    @property
    def single_rows(self) -> int:
        # After t steps the light cone from one cell spans 2t + 1 cells, so
        # t + 1 rows is the most that fits the window without cropping it.
        return (self.window + 1) // 2

    @property
    def cell_width(self) -> int:
        return self.window + self.gap

    @property
    def cell_height(self) -> int:
        return self.single_rows + 2 + self.random_rows + self.label_height + self.gap

    @property
    def width(self) -> int:
        return 2 * self.margin + self.columns * self.cell_width - self.gap


def poster(
    classes: dict[int, str], layout: Layout | None = None, seed: int = SEEDS[0], width: int = RING
) -> str:
    """One SVG with all 256 rules, grouped by class, each shown twice:

    from a single black cell for window // 2 steps (the whole light cone),
    and from the same random row for `random_rows` steps.
    """
    lay = layout or Layout()
    start = random_row(seed, width)
    reps = {members[0] for members in equivalence_classes()}
    body: list[str] = []
    y = lay.margin
    body.append(
        f'<text x="{lay.margin}" y="{y + 24}" class="title">'
        "The 256 elementary cellular automata, grouped by behaviour</text>"
    )
    body.append(
        f'<text x="{lay.margin}" y="{y + 44}" class="sub">'
        f"Each rule from a single black cell (top) and from the same random row (bottom), "
        f"a {lay.window}-cell window of a {width}-cell ring. "
        f"Bold numbers are the smallest rule in each mirror/complement class; "
        f"the other {256 - len(reps)} rules are their reflections and negatives.</text>"
    )
    y += 64
    for kind in KINDS:
        rules = sorted(rule for rule, k in classes.items() if k == kind)
        if not rules:
            continue
        y += lay.heading_height
        body.append(
            f'<text x="{lay.margin}" y="{y - 14}" class="heading">'
            f"{kind.capitalize()} · {len(rules)} rules · {DESCRIPTIONS[kind]}</text>"
        )
        for i, rule in enumerate(rules):
            col, row_index = i % lay.columns, i // lay.columns
            x = lay.margin + col * lay.cell_width
            top = y + row_index * lay.cell_height
            single = [
                crop(r, width, lay.window)
                for r in run(rule, single_cell(width), lay.single_rows - 1, width)
            ]
            noisy = [
                crop(r, width, lay.window) for r in run(rule, start, lay.random_rows - 1, width)
            ]
            body.append(f'<g id="rule-{rule}">')
            body.append(image_element(single, lay.window, x, top))
            body.append(image_element(noisy, lay.window, x, top + lay.single_rows + 2))
            weight = ' class="rep"' if rule in reps else ""
            body.append(
                f'<text x="{x}" y="{top + lay.single_rows + 2 + lay.random_rows + 11}"{weight}>'
                f"{rule}</text>"
            )
            body.append("</g>")
        y += math.ceil(len(rules) / lay.columns) * lay.cell_height
    height = y + lay.margin
    style = (
        "text{font-family:Helvetica,Arial,sans-serif;font-size:10px;fill:#444}"
        ".rep{font-weight:bold;fill:#111}"
        ".title{font-size:22px;fill:#111}"
        ".sub{font-size:11px;fill:#666}"
        ".heading{font-size:14px;fill:#111}"
        "image{image-rendering:pixelated;image-rendering:crisp-edges}"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {lay.width} {height}" '
        f'width="{lay.width}" height="{height}">\n'
        f"<style>{style}</style>\n"
        f'<rect width="{lay.width}" height="{height}" fill="#ffffff"/>\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )


# --- command line --------------------------------------------------------------


def summary(classes: dict[int, str]) -> str:
    lines = []
    for kind in KINDS:
        rules = sorted(rule for rule, k in classes.items() if k == kind)
        reps = [rule for rule in rules if representative(rule) == rule]
        lines.append(f"{kind}: {len(rules)} rules in {len(reps)} classes")
        lines.append("  " + " ".join(str(rule) for rule in reps))
    return "\n".join(lines)


def table(seeds: tuple[int, ...] = SEEDS) -> str:
    """One line per equivalence class with its verdict and per-seed measures."""
    lines = []
    for members in equivalence_classes():
        measures = [measure(members[0], seed) for seed in seeds]
        cells = []
        for m in measures:
            if m.homogeneous:
                cells.append("uniform")
            elif m.transient is not None:
                cells.append(f"period {m.period} after {m.transient}")
            else:
                cells.append(f"{m.kind} s={m.structure:+.2f}")
        lines.append(
            f"{members[0]:3d} {str(list(members)):22s} {verdict(measures):9s} " + " | ".join(cells)
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, help="write the poster SVG here")
    parser.add_argument("--rule", type=int, help="print one rule from a single cell as text")
    parser.add_argument("--steps", type=int, default=16, help="steps to print with --rule")
    parser.add_argument("--table", action="store_true", help="print every class's measures")
    parser.add_argument("--window", type=int, default=Layout.window, help="cells per thumbnail")
    args = parser.parse_args(argv)

    if args.rule is not None:
        if not 0 <= args.rule < 256:
            parser.error("rule must be between 0 and 255")
        width = 2 * args.steps + 1
        rows = run(args.rule, single_cell(width), args.steps, width)
        print(render_text(rows, width))
        return 0
    if args.table:
        print(table())
        return 0
    if args.out is None:
        parser.error("nothing to do: pass --out, --rule or --table")
    if not 1 <= args.window <= RING:
        parser.error(f"window must be between 1 and {RING}, the ring size")

    classes = classify_all()
    svg = poster(classes, Layout(window=args.window))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, encoding="utf-8")
    print(summary(classes), file=sys.stderr)
    print(f"wrote {args.out} ({len(svg) // 1024} KB)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
