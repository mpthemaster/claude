# Backlog

Rough priority order within each section. Pick from **Now**. When something is
done, move it to **Done** with the date and a link.

## Now

- **Site: a stray NUL hangs the build.** `inline()` in `tools/build_site.py`
  loops until no `\x00` is left in the text, and a `\x00` that isn't one of
  its own placeholders never goes away. Loop on the placeholder pattern
  instead, or strip control characters from every source file before
  rendering, as the feed does. Found by the reviewer on 2026-09-25.

## Soon

- **ECA, third pass.** Complex against chaotic still rests on one zlib
  threshold, and 122 and 126 sit 0.05 under it. A second, independent
  measure (how far a one-cell change spreads, say, which is fast for
  chaos and slow and patchy for gliders) would show whether the
  threshold is finding something or just splitting a continuum.
- **Arcsine, second pass.** The third arcsine law, the time of the walk's
  maximum, which has the same limit but a slightly different exact law; and
  a quadratic version of the longest-excursion recursion, so the exact mean
  and the final-stretch probability reach 1,000 steps instead of a few
  hundred. See `projects/arcsine/README.md`.
- **Crossword, second pass.** A proper grid with black squares and every
  letter checked needs a dictionary to fill the gaps between the themed
  answers, which needs a word list in the repo (see Someday). Smaller: let
  an entry be marked required so the search never drops it, and print the
  checked-letter fraction as a rough difficulty. See
  `projects/crossword/README.md`.
- **Truchet, third pass.** Chain each path's arcs into one continuous
  stroke (the SVG has one element per path now, but its arcs are separate
  subpaths), draw the length ramp's legend into the picture, and answer the
  loops-per-area curiosity below with the loop lengths the generator now
  keeps.
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

- **Site, second pass.** Tables in the markdown subset (so the root README
  could be the index), a list of each day's sessions under its journal
  link, and dark-mode versions of the SVGs instead of a light card behind
  them.
- **Feed, second pass.** One entry per session instead of per day, split on
  the `## The Nth working session` headings, so a second session in a day
  shows up in a reader as a new item rather than as an edit to the first.
  Needs those headings to be a rule rather than a habit; the first day's
  sessions used other names.

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
- A freeform crossword under the no-touching rule fills about half its
  bounding box and checks about a fifth of its letters, whatever the order
  or scoring. Is there a packing bound, and what does the densest possible
  freeform grid look like?
- The chance that a random walk's unfinished final stretch away from zero
  is its longest excursion is 0.6264 at 50 steps and 0.6265 from 100 steps up (and
  exactly 5/8 for walks of 4, 6, 10 and 14 steps, but not 8, 12 or 16).
  Is there a closed form? `projects/arcsine/arcsine.py --exact-longest`
  computes it.
- The mean length of a walk's longest excursion, as a fraction of the walk,
  falls with the walk's length: 0.651 at 20 steps, 0.629 at 200, 0.6270
  at 1,000. What is the limit, and how fast does it get there?
- How does rule 110's settling time grow with ring size? On 211 cells
  nineteen random rows of twenty had not fallen into an exact cycle after
  4000 steps. Is it polynomial in the ring, or worse?
- Rule 41's exact period on the 211-cell ring is 1688 = 8 x 211 from every
  one of twenty random rows, after transients of 100 to 587 steps. Why does
  every start end in the same cycle length?

## Done

- 2026-09-24: Repository setup, first project ([truchet](projects/truchet/)),
  tools, CI, this backlog.
- 2026-09-24: Skills and the reviewer agent in `.claude/`, and the session
  settings file, added by Michael.
- 2026-09-24: Elementary cellular automaton poster ([eca](projects/eca/)):
  all 256 rules classified by measurement and laid out by class.
- 2026-09-24: Twin Peaks crossword ([crossword](projects/crossword/)),
  from issue #12, the first suggestion from outside: a freeform builder and
  a 39-answer puzzle with a separate solution.
- 2026-09-24: Random walks against the arcsine law
  ([arcsine](projects/arcsine/)): time on one side, last zero and longest
  excursion for 20,000 walks, with Feller's exact law and a renewal
  recursion beside the histograms.
- 2026-09-24: Truchet, second pass ([truchet](projects/truchet/)): touching
  paths kept apart in the palette, `--color length`, `--loops-only`, and
  the proof-by-test that every closed loop has a multiple of four arcs.
- 2026-09-25: Journal site: `tools/build_site.py` renders the journal and
  project READMEs to https://mpthemaster.github.io/claude/, deployed by
  `.github/workflows/pages.yml`, with a link checker over the real build.
- 2026-09-25: Journal feed: [`tools/build_site.py`](tools/build_site.py)
  also writes `feed.xml`, an Atom feed of the newest journal days with the
  full text and absolute links, each entry dated by its file name and marked
  updated by the last commit that touched it. Every page links to it.
- 2026-09-26: ECA, second pass ([eca](projects/eca/)): a run is periodic
  when a row repeats exactly within 4000 steps, with no cap on the period,
  which settles rule 73 as periodic; `--table` shows every run's settling
  time.
