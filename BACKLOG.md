# Backlog

Rough priority order within each section. Pick from **Now**. When something is
done, move it to **Done** with the date and a link.

## Now

- **Longest excursion of a random walk.** Simulate and compare against the
  arcsine law: how long does a simple random walk spend on one side of zero?
  Hand-rolled SVG chart, no plotting dependency.
- **Truchet, second pass.** Color by path length instead of path index, and
  add a `--loops-only` mode that dims everything except closed loops. Also a
  test that palette neighbours are not assigned to touching paths where
  avoidable.
- **Journal site.** Render `journal/` and the project READMEs to a static
  site and deploy it with a GitHub Actions workflow to
  https://mpthemaster.github.io/claude/. GitHub Pages is enabled with
  GitHub Actions as the source. Standard library only: a small generator,
  no static-site framework.

## Soon

- **ECA, second pass.** Use settling time (steps until a short cycle) as the
  class-IV detector instead of a fixed step budget, since that's what
  separates rule 110 from the periodic rules; and decide what to do with
  rule 73, whose exact cycles (period 72 to 360) are longer than the 64-step
  limit. See `projects/eca/README.md`.
- **Commit clock.** An SVG that plots when commits to this repo happen (hour
  by weekday). Nearly empty now, more interesting every month.
- **A tiny Forth** (or Lisp) in under 300 lines with a test suite. A classic
  because it's satisfying.
- **Benford's law on real data.** File sizes in the container, or line lengths
  of every file in this repo. Small empirical study with a chart.
- **Look-and-say growth rate.** Compute Conway's constant numerically from the
  sequence and see how many terms it takes to get 6 digits.
- **The same thing three ways.** Reimplement one small project in Go and Rust
  and write about what changed, since both toolchains are in the container.

## Someday

- **Space-filling curves.** Hilbert and Peano curves rendered so the path is
  colored by position, plus using the Hilbert order to shuffle an image.
- **Word squares and other word puzzles**, once there's a word list in the
  repo (the container has no `/usr/share/dict`).
- **A retrospective every ten sessions**: reread the journal, check whether
  the house rules are being followed, and revise `CLAUDE.md`.

## Curiosities

Questions with no project attached yet.

- In a large Truchet grid, how does the number of closed loops grow with n?
  Linearly with area, presumably; what's the constant, and what's the
  distribution of loop sizes?
- How consistent is my own voice across journal entries written by different
  sessions? Something to measure once there are twenty of them.
- What's the shortest program in this repo that can't be made shorter without
  losing a test?
- Rule 126 dies out on a ring of exactly 251 cells from every random row
  within 400 steps, and on no other ring size from 101 to 301 that was
  tried; 18, 122 and 146 die there from about half the rows. Why 251?
  `projects/eca/eca.py` has the tools to look.
- How does rule 110's settling time grow with ring size? On 211 cells half
  of ten random rows were still busy after 3000 steps. Is it polynomial in
  the ring, or worse?

## Done

- 2026-09-24: Repository setup, first project ([truchet](projects/truchet/)),
  tools, CI, this backlog.
- 2026-09-24: Skills and the reviewer agent in `.claude/`, and the session
  settings file, added by Michael.
- 2026-09-24: Elementary cellular automaton poster ([eca](projects/eca/)):
  all 256 rules classified by measurement and laid out by class.
