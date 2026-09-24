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
"""

from __future__ import annotations

import argparse
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
    hues. When no entry is two steps clear (a path hemmed in by four others
    whose colors are spread around the palette), one step clear is accepted,
    and only when even that is impossible may a color repeat. Ties go to the
    lowest index, which keeps the result deterministic.
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


def arc_path(arc: Arc, s: float) -> str:
    x0, y0 = arc.col * s, arc.row * s
    start = midpoint(arc.a, x0, y0, s)
    end = midpoint(arc.b, x0, y0, s)
    center = corner(arc.a, arc.b, x0, y0, s)
    r = s / 2
    flag = sweep_flag(start, end, center)
    return f"M{start[0]:g},{start[1]:g} A{r:g},{r:g} 0 0 {flag} {end[0]:g},{end[1]:g}"


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
    stroke = s * 0.34
    colors = path_colors(tiling, color)
    segments: list[list[str]] = [[] for _ in range(tiling.path_count)]
    for arc in tiling.arcs:
        segments[arc.path_id].append(arc_path(arc, s))
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {width:g}" '
        f'width="{width:g}" height="{width:g}">',
        f'  <rect width="{width:g}" height="{width:g}" fill="{background}"/>',
        f'  <g fill="none" stroke-width="{stroke:g}" stroke-linecap="round">',
    ]
    for pid, parts in enumerate(segments):
        shade = DIM if loops_only and not tiling.loops[pid] else colors[pid]
        lines.append(f'    <path d="{" ".join(parts)}" stroke="{shade}"/>')
    lines.append("  </g>")
    lines.append("</svg>")
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
    args = parser.parse_args(argv)

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
