"""Truchet tilings with per-path coloring.

A Truchet tile holds two quarter-circle arcs joining the midpoints of its
edges. Type 0 joins north-east and south-west; type 1 joins north-west and
south-east. Laid out on a grid, the arcs meet at shared edge midpoints and
form continuous paths: some run border to border, others close into loops.

This module generates a seeded grid, groups the arcs into paths with a
union-find over edge midpoints, and writes an SVG where every path has its
own color.

Usage:
    python truchet.py --size 24 --seed 7 --out out/seed-7.svg
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
    path_count: int
    loop_count: int

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
    touches_boundary: dict[int, bool] = {}
    arcs: list[Arc] = []
    for r in range(n):
        for c in range(n):
            nodes = tile_nodes(r, c)
            for a, b in tile_arcs(tiles[r][c]):
                root = uf.find(nodes[a])
                pid = path_ids.setdefault(root, len(path_ids))
                if is_boundary(nodes[a], n) or is_boundary(nodes[b], n):
                    touches_boundary[pid] = True
                touches_boundary.setdefault(pid, False)
                arcs.append(Arc(r, c, a, b, pid))

    loops = sum(1 for hits in touches_boundary.values() if not hits)
    return Tiling(n, seed, tiles, arcs, len(path_ids), loops)


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


def render_svg(tiling: Tiling, tile_px: float = 32, background: str = "#14151a") -> str:
    """Render the tiling as an SVG document string."""
    n, s = tiling.n, tile_px
    width = n * s
    stroke = s * 0.34
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {width:g}" '
        f'width="{width:g}" height="{width:g}">',
        f'  <rect width="{width:g}" height="{width:g}" fill="{background}"/>',
        f'  <g fill="none" stroke-width="{stroke:g}" stroke-linecap="round">',
    ]
    for arc in tiling.arcs:
        color = PALETTE[arc.path_id % len(PALETTE)]
        lines.append(f'    <path d="{arc_path(arc, s)}" stroke="{color}"/>')
    lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--size", type=int, default=24, help="grid size (default 24)")
    parser.add_argument("--seed", type=int, default=7, help="random seed (default 7)")
    parser.add_argument("--tile", type=float, default=32, help="tile size in px (default 32)")
    parser.add_argument("--out", type=Path, help="write SVG here (default: stdout)")
    args = parser.parse_args(argv)

    tiling = generate(args.size, args.seed)
    svg = render_svg(tiling, args.tile)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(svg)
        print(
            f"{args.size}x{args.size} seed {args.seed}: {tiling.path_count} paths "
            f"({tiling.open_path_count} open, {tiling.loop_count} loops) -> {args.out}",
            file=sys.stderr,
        )
    else:
        sys.stdout.write(svg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
