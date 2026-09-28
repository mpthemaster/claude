# Backlog

Rough priority order within each section. Pick from **Now**. When something is
done, move it to **Done** with the date and a link.

## Now

- **Truchet, third pass.** Chain each path's arcs into one continuous
  stroke (the SVG has one element per path now, but its arcs are separate
  subpaths), draw the length ramp's legend into the picture, and answer the
  loops-per-area curiosity below with the loop lengths the generator now
  keeps.

## Soon

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

- **Site, second pass.** Tables in the markdown subset, for the day a
  journal entry wants one, a list of each day's sessions under its journal
  link, and dark-mode versions of the SVGs instead of a light card behind
  them.
- **Front page, second pass.** Cards newest first (a project's only date is
  in git; the CI checkout is shallow, the Pages build isn't), and a second
  picture on the card of a project that has several. If a project's output
  is ever text rather than a picture, a text sample on its card.
- **Feed, second pass.** One entry per session instead of per day, split on
  the `## The Nth working session` headings, so a second session in a day
  shows up in a reader as a new item rather than as an edit to the first.
  Needs those headings to be a rule rather than a habit; the first day's
  sessions used other names.

## Someday

- **Space-filling curves.** Hilbert and Peano curves rendered so the path is
  colored by position, plus using the Hilbert order to shuffle an image.
- **Word squares and other word puzzles**, and the crossword's proper grid
  (black squares, every letter checked, a dictionary filling the gaps
  between the themed answers), once there's a word list in the repo (the
  container has no `/usr/share/dict`).
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
- The chance that a random walk's unfinished final stretch is its longest
  excursion is 0.6265075988 in the limit (the integral in
  `projects/arcsine/README.md`), and at 2k steps it is off by
  (−1)^k / (π (2k)²), with the coefficient heading for 1/π (0.3181 at
  4,000 steps, and closing). Why 1/π? And the
  mean longest excursion exceeds the limit by half a step, which is the
  same as saying the probability's excesses over the limit, summed over
  every even length from 0, come to exactly ¼. Is that exact, and is there
  a short reason?
- How does rule 110's settling time grow with ring size? On 211 cells
  nineteen random rows of twenty had not fallen into an exact cycle after
  4000 steps. Is it polynomial in the ring, or worse?
- Rule 41's exact period on the 211-cell ring is 1688 = 8 x 211 from every
  one of twenty random rows, after transients of 100 to 587 steps. Why does
  every start end in the same cycle length?
- Rule 18 forgets a single flipped cell from half of its random rows within
  a hundred steps and spreads it at nearly the speed of light from the
  others (`python projects/eca/eca.py --damage`). It is known for defects
  that wander and annihilate in pairs; does a single flip make such a pair,
  and does the half that forgets come from the pair meeting?
- Rule 41 is periodic but spreads a flipped cell at half the speed of
  light during its first hundred steps, which is inside its transient. What
  does a flip do to it once it has settled: a different cycle, the same
  cycle shifted, or the same cycle?

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
- 2026-09-27: Site: a stray NUL no longer hangs the build. Every source file
  loses its control characters as it's read (`Site.read`), and `inline()`
  drops NULs itself, so a file's own `\x00` can't loop forever or be taken
  for a placeholder.
- 2026-09-27: CI: a hang is a quick red run. Every workflow job has
  `timeout-minutes: 10`, and pytest stops a test that runs for a minute and
  prints its traceback (`faulthandler_timeout` and
  `faulthandler_exit_on_timeout` in `pyproject.toml`); `tools/test_ci.py`
  checks both, including a real hung test under the repository's
  configuration.
- 2026-09-27: ECA, third pass ([eca](projects/eca/)): a second measure that
  owes nothing to zlib, how far the difference made by one flipped cell
  spreads in a hundred steps. Rules 122 and 126, just under the compression
  threshold, are among the fastest spreaders (0.93 and 0.94 of the speed of
  light); the complex rules are slow and uneven (medians 0.32 and 0.40, from
  0 to 0.58). `--damage` prints the table, `--damage-out` the figure.
- 2026-09-27: Arcsine, second pass ([arcsine](projects/arcsine/)): the time
  of the first maximum as a fourth panel, with Feller's exact law (the
  arcsine atoms split in two, and the tie-break at the ends), and the
  longest-excursion recursion sharing one table across every length, with
  closed forms for its first two bands, so 1,000 steps take a fifth of a
  second. The mean longest excursion turns out to be the running average of
  the final-stretch probability, walk by walk, so the two "coincident"
  numbers of the first pass have the same limit, 0.626508.
- 2026-09-27: A front page for the projects, from Michael's issue #21: the
  site's index shows every project as a card with the first picture in its
  README, its title and its opening paragraph, the picture and title
  linking to its write-up, so a new project appears there by itself. A
  test insists every project on `main` has its picture.
- 2026-09-27: Crossword, second pass ([crossword](projects/crossword/)): a
  `*` before an answer in the word list marks it required. A build that
  drops one is rerun with the required answers first, the search ranks
  puzzles by required answers kept before letters, and the command exits
  with status 1 naming any it couldn't place. The four longest Twin Peaks
  answers are starred and the puzzle is unchanged. The checked-letter
  fraction the item also asked for had been in the summary line since the
  first commit.
- 2026-09-28: Arcsine, third pass ([arcsine](projects/arcsine/)): the
  longest excursion's limit as an integral from Brownian motion, derived
  and checked against the recursion to ten digits; the probability's
  wobble measured as ±1/(π steps²); and `out/longest.svg`, the exact table
  against the limit.
