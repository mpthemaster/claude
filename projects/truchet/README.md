# Truchet tilings, colored by path

A Truchet tile holds two quarter-circle arcs joining the midpoints of its
edges, in one of two orientations. Tile a grid with random orientations and
the arcs join up into meandering paths. This generator does that from a seed,
then works out which arcs belong to the same path and gives each path its own
color.

<p align="center">
  <img src="out/seed-7.svg" width="480" alt="24 by 24 tiling, seed 7">
</p>

## Run

```sh
python projects/truchet/truchet.py --size 24 --seed 7 --out projects/truchet/out/seed-7.svg
python projects/truchet/truchet.py --size 16 --seed 3 --tile 40 > seed-3.svg
pytest projects/truchet
```

Writing to `--out` also prints a one-line summary:
`24x24 seed 7: 86 paths (48 open, 38 loops)`.

## How it works

- Every arc joins two edge midpoints of its tile. Neighbouring tiles share
  midpoints, so a union-find over midpoints groups arcs into paths in a single
  pass over the grid.
- Paths are numbered in order of first appearance (row-major), which keeps the
  output deterministic for a given seed. Colors come from a twelve-color
  palette by path number.
- A path that touches the border is open; one that doesn't is a closed loop.
  The summary line counts both.

## Two things worth knowing

**An n×n grid always has exactly 2n open paths.** Each border midpoint is the
end of exactly one path, there are 4n border midpoints, and each open path has
two ends. Everything else is a loop. `test_open_paths_is_always_two_n` checks
this for several sizes and seeds.

**SVG arcs need a sweep flag, and the obvious guess is a coin flip.** Through
any two adjacent midpoints there are two quarter circles of radius half a tile:
one centred on the tile's corner (the Truchet one) and one centred on the
tile's middle. The sign of the cross product of the start and end vectors,
taken from the corner, picks the corner-centred arc without hard-coding four
cases. Since SVG's y axis points down, a positive cross product means
clockwise on screen, which is sweep flag 1.

## Files

- `truchet.py`: generator, path grouping, SVG rendering, and a small CLI.
- `test_truchet.py`: determinism, the 2n invariant, loop detection on a 2×2
  grid, and the sweep-flag derivation.
- `out/seed-7.svg`, `out/seed-3.svg`: committed samples.
