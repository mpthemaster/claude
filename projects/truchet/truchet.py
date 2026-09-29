"""Truchet tilings with per-path coloring.

A Truchet tile holds two quarter-circle arcs joining the midpoints of its
edges. Type 0 joins north-east and south-west; type 1 joins north-west and
south-east. Laid out on a grid, the arcs meet at shared edge midpoints and
form continuous paths: some run border to border, others close into loops.

This module generates a seeded grid, groups the arcs into paths with a
union-find over edge midpoints, and writes an SVG where every path has its
own color. Colors are assigned so that paths sharing a tile are kept apart in
the palette, or, with --color length, taken from a ramp by the path's length.
--loops-only dims every path that reaches the border.

Usage:
    python truchet.py --size 24 --seed 7 --out out/seed-7.svg
    python truchet.py --color length --out out/seed-7-length.svg
    python truchet.py --loops-only --out out/seed-7-loops.svg
    python truchet.py --size 128 --census 64
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

# Node = an edge midpoint of the grid. ("h", r, c) is the midpoint of the
# horizontal edge above row r in column c (so r ranges 0..n). ("v", r, c) is
# the midpoint of the vertical edge left of column c in row r (c ranges 0..n).
Node = tuple[str, int, int]

# Twelve colors for --color path. Neighbouring entries are similar hues, which
# is why assign_palette keeps touching paths two steps apart where it can.
PALETTE = [
    "#f94144",
    "#f3722c",
    "#f8961e",
    "#f9c74f",
    "#90be6d",
    "#43aa8b",
    "#4d908e",
    "#577590",
    "#277da1",
    "#b5179e",
    "#7209b7",
    "#4cc9f0",
]

# One color per doubling of path length for --color length: entry k is for
# paths of 2**k to 2**(k+1) - 1 arcs, and the last entry takes everything longer.
LENGTH_RAMP = [
    "#fff3b0",
    "#ffd166",
    "#f8961e",
    "#f3722c",
    "#f94144",
    "#e5397d",
    "#b5179e",
    "#7209b7",
    "#5f3dc4",
    "#4361ee",
    "#4cc9f0",
    "#90e0ef",
]

COLOR_MODES = ("path", "length")
BACKGROUND = "#14151a"
DIM = "#2a2c33"
LEGEND_TEXT = "#c9ccd6"
LEGEND_CAPTION = "#8a8e9c"
LEGEND_TILES = 1.9  # height of the --color length legend strip, in tiles
LEGEND_CAPTION_TEXT = "arcs per path"
TEXT_WIDTH = 0.6  # a generous average glyph width, in font sizes, for sans-serif digits


class UnionFind:
    """Minimal disjoint-set forest with path halving and union by size."""

    def __init__(self) -> None:
        self.parent: dict[Node, Node] = {}
        self.size: dict[Node, int] = {}

    def add(self, x: Node) -> None:
        if x not in self.parent:
            self.parent[x] = x
            self.size[x] = 1

    def find(self, x: Node) -> Node:
        self.add(x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: Node, b: Node) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        self.size[ra] += self.size[rb]


def tile_nodes(r: int, c: int) -> dict[str, Node]:
    """The four edge-midpoint nodes around tile (r, c)."""
    return {
        "N": ("h", r, c),
        "S": ("h", r + 1, c),
        "W": ("v", r, c),
        "E": ("v", r, c + 1),
    }


def tile_arcs(kind: int) -> tuple[tuple[str, str], tuple[str, str]]:
    """Which edge midpoints each arc of a tile joins, by tile type."""
    return (("N", "E"), ("S", "W")) if kind == 0 else (("N", "W"), ("S", "E"))


def is_boundary(node: Node, n: int) -> bool:
    kind, r, c = node
    return (kind == "h" and r in (0, n)) or (kind == "v" and c in (0, n))


@dataclass(frozen=True)
class Arc:
    row: int
    col: int
    a: str  # edge letter, e.g. "N"
    b: str  # edge letter, e.g. "E"
    path_id: int


@dataclass
class Tiling:
    n: int
    seed: int
    tiles: list[list[int]]
    arcs: list[Arc]
    lengths: list[int]  # arcs per path, indexed by path id
    loops: list[bool]  # True for a path that never reaches the border

    @property
    def path_count(self) -> int:
        return len(self.lengths)

    @property
    def loop_count(self) -> int:
        return sum(self.loops)

    @property
    def open_path_count(self) -> int:
        return self.path_count - self.loop_count


def generate(n: int, seed: int) -> Tiling:
    """Build an n x n tiling and group its arcs into paths."""
    if n < 1:
        raise ValueError("size must be at least 1")
    rng = random.Random(seed)
    tiles = [[rng.randrange(2) for _ in range(n)] for _ in range(n)]

    uf = UnionFind()
    for r in range(n):
        for c in range(n):
            nodes = tile_nodes(r, c)
            for a, b in tile_arcs(tiles[r][c]):
                uf.union(nodes[a], nodes[b])

    # Number the paths in order of first appearance so output is deterministic.
    path_ids: dict[Node, int] = {}
    lengths: list[int] = []
    loops: list[bool] = []
    arcs: list[Arc] = []
    for r in range(n):
        for c in range(n):
            nodes = tile_nodes(r, c)
            for a, b in tile_arcs(tiles[r][c]):
                root = uf.find(nodes[a])
                pid = path_ids.get(root)
                if pid is None:
                    pid = path_ids[root] = len(path_ids)
                    lengths.append(0)
                    loops.append(True)
                lengths[pid] += 1
                if is_boundary(nodes[a], n) or is_boundary(nodes[b], n):
                    loops[pid] = False
                arcs.append(Arc(r, c, a, b, pid))

    return Tiling(n, seed, tiles, arcs, lengths, loops)


def torus_loop_lengths(n: int, seed: int) -> list[int]:
    """Arcs per loop of the same n x n tiling as generate(n, seed), on a torus.

    The bottom edge is glued to the top and the right to the left, so there is
    no border and every path closes. Used only for counting: some loops wrap
    around the torus and can't be drawn on the flat grid.
    """
    if n < 2 or n % 2:
        raise ValueError("a torus needs an even size, so the corners still checkerboard")
    rng = random.Random(seed)
    tiles = [[rng.randrange(2) for _ in range(n)] for _ in range(n)]
    uf = UnionFind()

    def glue(node: Node) -> Node:
        kind, r, c = node
        return (kind, r % n, c % n)

    for r in range(n):
        for c in range(n):
            nodes = tile_nodes(r, c)
            for a, b in tile_arcs(tiles[r][c]):
                uf.union(glue(nodes[a]), glue(nodes[b]))
    lengths: dict[Node, int] = {}
    for r in range(n):
        for c in range(n):
            nodes = tile_nodes(r, c)
            for a, _ in tile_arcs(tiles[r][c]):
                root = uf.find(glue(nodes[a]))
                lengths[root] = lengths.get(root, 0) + 1
    return list(lengths.values())


def touching_pairs(tiling: Tiling) -> set[tuple[int, int]]:
    """Unordered pairs of distinct paths that share a tile.

    The two arcs of a tile come within 0.41 tile widths of each other. Arcs in
    different tiles are either joined at a shared midpoint (so they belong to
    the same path) or at least half a tile apart. So sharing a tile is the
    only way two paths come close on the page.
    """
    by_tile: dict[tuple[int, int], list[int]] = {}
    for arc in tiling.arcs:
        by_tile.setdefault((arc.row, arc.col), []).append(arc.path_id)
    pairs: set[tuple[int, int]] = set()
    for first, second in by_tile.values():
        if first != second:
            pairs.add((min(first, second), max(first, second)))
    return pairs


def palette_distance(a: int, b: int, size: int) -> int:
    """Steps between two palette entries, the palette being a cycle."""
    d = abs(a - b) % size
    return min(d, size - d)


def assign_palette(tiling: Tiling, size: int = len(PALETTE)) -> list[int]:
    """A palette index per path, keeping touching paths apart where possible.

    Paths are colored in order of first appearance. Each takes the least-used
    entry that is at least two steps from every already-colored path it
    touches, so touching paths get neither the same color nor neighbouring
    hues. When no entry is two steps clear (a path hemmed in by at least four
    already-colored paths whose colors between them block every entry), one
    step clear is accepted, and only when even that is impossible may a color
    repeat. Ties go to the lowest index, which keeps the result deterministic.
    """
    neighbours: list[set[int]] = [set() for _ in range(tiling.path_count)]
    for a, b in touching_pairs(tiling):
        neighbours[a].add(b)
        neighbours[b].add(a)
    chosen: list[int] = []
    used = [0] * size
    for pid in range(tiling.path_count):
        taken = {chosen[q] for q in neighbours[pid] if q < pid}
        scores = []
        for k in range(size):
            gap = min((palette_distance(k, c, size) for c in taken), default=size)
            scores.append((min(gap, 2), -used[k], -k, k))
        best = max(scores)[-1]
        chosen.append(best)
        used[best] += 1
    return chosen


def length_bucket(length: int) -> int:
    """Index into LENGTH_RAMP: floor(log2(length)), capped at the last entry."""
    if length < 1:
        raise ValueError("a path has at least one arc")
    return min(length.bit_length() - 1, len(LENGTH_RAMP) - 1)


def path_colors(tiling: Tiling, color: str = "path") -> list[str]:
    """One color per path: by palette assignment, or by length on a ramp."""
    if color == "path":
        return [PALETTE[k] for k in assign_palette(tiling)]
    if color == "length":
        return [LENGTH_RAMP[length_bucket(m)] for m in tiling.lengths]
    raise ValueError(f"color must be one of {COLOR_MODES}, not {color!r}")


def midpoint(edge: str, x0: float, y0: float, s: float) -> tuple[float, float]:
    half = s / 2
    return {
        "N": (x0 + half, y0),
        "E": (x0 + s, y0 + half),
        "S": (x0 + half, y0 + s),
        "W": (x0, y0 + half),
    }[edge]


def corner(a: str, b: str, x0: float, y0: float, s: float) -> tuple[float, float]:
    """The tile corner shared by two adjacent edges, e.g. N and E -> top right."""
    edges = {a, b}
    x = x0 + s if "E" in edges else x0
    y = y0 + s if "S" in edges else y0
    return x, y


def sweep_flag(
    start: tuple[float, float], end: tuple[float, float], center: tuple[float, float]
) -> int:
    """SVG sweep flag for the arc from start to end that is centred on center.

    SVG's y axis points down, so a positive cross product means the rotation
    from the start vector to the end vector is clockwise on screen, which is
    sweep-flag 1.
    """
    sx, sy = start[0] - center[0], start[1] - center[1]
    ex, ey = end[0] - center[0], end[1] - center[1]
    return 1 if sx * ey - sy * ex > 0 else 0


def arc_step(a: str, b: str, arc: Arc, s: float) -> str:
    """The SVG arc command from arc's midpoint a to its midpoint b.

    The pen is assumed to be at midpoint a already; a and b may be the arc's
    own ends in either order, so a chained path can walk an arc backwards.
    """
    x0, y0 = arc.col * s, arc.row * s
    start = midpoint(a, x0, y0, s)
    end = midpoint(b, x0, y0, s)
    center = corner(a, b, x0, y0, s)
    r = s / 2
    flag = sweep_flag(start, end, center)
    return f"A{r:g},{r:g} 0 0 {flag} {end[0]:g},{end[1]:g}"


# A step along a chained path: the arc, and the edge letters it is walked
# from and to.
Step = tuple[Arc, str, str]


def chain_paths(tiling: Tiling) -> list[list[Step]]:
    """Each path's arcs in walking order, oriented so each ends where the next starts.

    An open path starts at the smaller of its two border midpoints; a loop
    starts at the first-named midpoint of its first arc in row-major order
    and walks that arc forwards. Either way the result is deterministic.
    """
    n = tiling.n
    at_node: list[dict[Node, list[int]]] = [{} for _ in range(tiling.path_count)]
    starts: list[Node | None] = [None] * tiling.path_count
    for i, arc in enumerate(tiling.arcs):
        nodes = tile_nodes(arc.row, arc.col)
        pid = arc.path_id
        for edge in (arc.a, arc.b):
            at_node[pid].setdefault(nodes[edge], []).append(i)
        if tiling.loops[pid]:
            if starts[pid] is None:
                starts[pid] = nodes[arc.a]
        else:
            for edge in (arc.a, arc.b):
                node = nodes[edge]
                if is_boundary(node, n) and (starts[pid] is None or node < starts[pid]):
                    starts[pid] = node

    chains: list[list[Step]] = []
    for pid in range(tiling.path_count):
        node = starts[pid]
        steps: list[Step] = []
        prev = -1
        while len(steps) < tiling.lengths[pid]:
            # A midpoint touches at most two arcs of a path; take the one we
            # didn't arrive by. (A loop's start node has two, and prev = -1 on
            # the first step picks the first-listed, the first arc.)
            i = next(j for j in at_node[pid][node] if j != prev)
            arc = tiling.arcs[i]
            nodes = tile_nodes(arc.row, arc.col)
            a, b = (arc.a, arc.b) if nodes[arc.a] == node else (arc.b, arc.a)
            steps.append((arc, a, b))
            node, prev = nodes[b], i
        chains.append(steps)
    return chains


def path_d(steps: list[Step], s: float, closed: bool) -> str:
    """SVG path data for one chained path: a single move, then every arc.

    A loop ends with Z so the stroke is joined where it closes, rather than
    meeting itself at two round caps.
    """
    first, a, _ = steps[0]
    x, y = midpoint(a, first.col * s, first.row * s, s)
    parts = [f"M{x:g},{y:g}"]
    parts += [arc_step(a, b, arc, s) for arc, a, b in steps]
    if closed:
        parts.append("Z")
    return " ".join(parts)


def bucket_label(k: int) -> str:
    """The range of arc counts LENGTH_RAMP entry k stands for, e.g. "4–7"."""
    low, high = 2**k, 2 ** (k + 1) - 1
    if k == len(LENGTH_RAMP) - 1:
        return f"{low}+"
    return str(low) if low == high else f"{low}–{high}"


def legend_svg(tiling: Tiling, width: float, s: float) -> list[str]:
    """A strip of LEGEND_TILES tile heights under the tiling explaining the ramp.

    One swatch per ramp entry from a single arc up to the entry of the
    longest path, so the legend shows the whole scale the picture uses and
    nothing it doesn't. The swatches share the width equally, and on a grid
    too small for the labels at their usual size the text shrinks to fit.
    """
    shown = length_bucket(max(tiling.lengths)) + 1
    cell = width / shown
    top = width + s * 0.35
    widest = max(len(bucket_label(k)) for k in range(shown))
    font = min(s * 0.34, 0.9 * cell / (TEXT_WIDTH * widest))
    caption_font = min(s * 0.34, 0.9 * width / (TEXT_WIDTH * len(LEGEND_CAPTION_TEXT)))
    lines = [
        f'  <g font-family="sans-serif" font-size="{font:g}" fill="{LEGEND_TEXT}" '
        f'text-anchor="middle">',
    ]
    for k in range(shown):
        x = k * cell
        lines.append(
            f'    <rect x="{x + s * 0.1:g}" y="{top:g}" width="{cell - s * 0.2:g}" '
            f'height="{s * 0.34:g}" rx="{s * 0.17:g}" fill="{LENGTH_RAMP[k]}"/>'
        )
        lines.append(
            f'    <text x="{x + cell / 2:g}" y="{top + s * 0.8:g}">{bucket_label(k)}</text>'
        )
    lines.append(
        f'    <text x="{width / 2:g}" y="{top + s * 1.3:g}" fill="{LEGEND_CAPTION}" '
        f'font-size="{caption_font:g}">{LEGEND_CAPTION_TEXT}</text>'
    )
    lines.append("  </g>")
    return lines


def render_svg(
    tiling: Tiling,
    tile_px: float = 32,
    background: str = BACKGROUND,
    color: str = "path",
    loops_only: bool = False,
) -> str:
    """Render the tiling as an SVG document string, one <path> element per path.

    With loops_only, every path that reaches the border is drawn in DIM so the
    closed loops stand out.
    """
    n, s = tiling.n, tile_px
    width = n * s
    legend = legend_svg(tiling, width, s) if color == "length" else []
    height = width + (s * LEGEND_TILES if legend else 0)
    stroke = s * 0.34
    colors = path_colors(tiling, color)
    chains = chain_paths(tiling)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" '
        f'width="{width:g}" height="{height:g}">',
        f'  <rect width="{width:g}" height="{height:g}" fill="{background}"/>',
        f'  <g fill="none" stroke-width="{stroke:g}" stroke-linecap="round">',
    ]
    for pid, steps in enumerate(chains):
        shade = DIM if loops_only and not tiling.loops[pid] else colors[pid]
        d = path_d(steps, s, tiling.loops[pid])
        lines.append(f'    <path d="{d}" stroke="{shade}"/>')
    lines.append("  </g>")
    lines.extend(legend)
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


# Loops per tile in an infinite tiling: the cluster density of critical bond
# percolation on the square lattice (Temperley and Lieb). See the README.
BULK_LOOP_DENSITY = (3 * math.sqrt(3) - 5) / 2


@dataclass
class Census:
    """Loop statistics over several tilings of one size."""

    n: int
    seeds: int
    loops_per_tile: list[float]  # one entry per tiling
    smallest_per_tile: list[float]  # 4-arc loops, one entry per tiling
    torus_per_tile: list[float]  # loops per tile of the same tilings on a torus
    by_bucket: dict[int, int]  # loops per length_bucket, summed over tilings

    @property
    def tiles(self) -> int:
        return self.seeds * self.n * self.n


def loop_census(n: int, seeds: int) -> Census:
    """Count the loops in the n x n tilings for seeds 0 .. seeds - 1."""
    if seeds < 1:
        raise ValueError("a census needs at least one seed")
    loops, smallest, torus = [], [], []
    by_bucket: dict[int, int] = {}
    for seed in range(seeds):
        t = generate(n, seed)
        lengths = [m for m, loop in zip(t.lengths, t.loops, strict=True) if loop]
        loops.append(len(lengths) / (n * n))
        smallest.append(lengths.count(4) / (n * n))
        for m in lengths:
            k = m.bit_length() - 1  # floor(log2), uncapped, unlike length_bucket
            by_bucket[k] = by_bucket.get(k, 0) + 1
        if n % 2 == 0:
            torus.append(len(torus_loop_lengths(n, seed)) / (n * n))
    return Census(n, seeds, loops, smallest, torus, dict(sorted(by_bucket.items())))


def mean_and_error(values: list[float]) -> tuple[float, float]:
    """Sample mean and its standard error (zero for a single value)."""
    mean = sum(values) / len(values)
    if len(values) < 2:
        return mean, 0.0
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    return mean, math.sqrt(var / len(values))


def census_report(c: Census) -> str:
    """A plain-text table of a census, for the CLI."""
    n = c.n
    loops, loops_err = mean_and_error(c.loops_per_tile)
    small, small_err = mean_and_error(c.smallest_per_tile)
    exact_small = (n - 1) ** 2 / (16 * n * n)
    lines = [
        f"loops in {c.seeds} tilings of {n}x{n} (seeds 0-{c.seeds - 1})",
        f"  loops per tile      {loops:.5f} ± {loops_err:.5f}   "
        f"bulk limit (3√3 − 5)/2 = {BULK_LOOP_DENSITY:.5f}",
        f"  4-arc loops / tile  {small:.5f} ± {small_err:.5f}   "
        f"exact (n − 1)²/16n² = {exact_small:.5f}",
    ]
    if c.torus_per_tile:
        torus, torus_err = mean_and_error(c.torus_per_tile)
        lines.append(f"  on a torus          {torus:.5f} ± {torus_err:.5f}")
    lines += [
        "",
        "  arcs        loops / tile   ratio to the row above",
    ]
    prev = None
    for k, count in c.by_bucket.items():
        low, high = 2**k, 2 ** (k + 1) - 1
        ratio = f"{count / prev:.3f}" if prev else ""
        lines.append(f"  {f'{low}–{high}':<10}  {count / c.tiles:.6f}       {ratio}")
        prev = count
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--size", type=int, default=24, help="grid size (default 24)")
    parser.add_argument("--seed", type=int, default=7, help="random seed (default 7)")
    parser.add_argument("--tile", type=float, default=32, help="tile size in px (default 32)")
    parser.add_argument(
        "--color",
        choices=COLOR_MODES,
        default="path",
        help="path: one color per path, touching paths kept apart (default); "
        "length: a ramp by the path's number of arcs",
    )
    parser.add_argument(
        "--loops-only", action="store_true", help="dim every path that reaches the border"
    )
    parser.add_argument("--out", type=Path, help="write SVG here (default: stdout)")
    parser.add_argument(
        "--census",
        type=int,
        metavar="SEEDS",
        help="instead of drawing, count the loops in SEEDS tilings of --size and print a table",
    )
    args = parser.parse_args(argv)

    if args.census is not None:
        if args.census < 1:
            parser.error("--census needs at least one seed")
        sys.stdout.write(census_report(loop_census(args.size, args.census)))
        return 0

    tiling = generate(args.size, args.seed)
    svg = render_svg(tiling, args.tile, color=args.color, loops_only=args.loops_only)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(svg)
        print(
            f"{args.size}x{args.size} seed {args.seed}: {tiling.path_count} paths "
            f"({tiling.open_path_count} open, {tiling.loop_count} loops), "
            f"longest {max(tiling.lengths)} arcs -> {args.out}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
