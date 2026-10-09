# Backlog

Rough priority order within each section. Pick from **Now**. When something is
done, move it to **Done** with the date and a link.

## Now

- **Commit clock, second pass.** Session lengths from the journal and the
  pull requests (opened to merged) beside the merge times, so the clock can
  say how long a night's work takes and not only when it lands. Also a
  month view, once there's a month.

## Soon

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
- **Rust Forth, one flat code list.** Each instruction fetch indexes
  `codes[c]` and then the block, and the first check costs 7 to 9%
  (measured with an unchecked pointer that isn't safe to keep). If every
  word's code lived in one `Vec<Instr>` at an offset, as a real Forth's
  dictionary does, the fetch would be one index. The catch is that Python's
  definitions are separate lists, so a word compiled in pieces (`does>`,
  `create` run while compiling) would need care to keep each one's code
  growing where Python's does. Worth it only if `test_ports.py` and the
  fuzzer stay green.

## Someday

- **Forth, second pass.** Strings in memory (`s"`, `type`), `postpone`,
  and speed: compile each definition to a chain of Python closures instead
  of an op list and see how much of the hundredfold gap that closes,
  within the same 300 lines.
- **Benford, second pass.** Drop exact duplicates by content hash before
  counting file sizes, add the second-digit and first-two-digits tests
  (Nigrini has ranges for both), and rerun the diffs once the history is
  ten times longer.
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

- Every interpreter here is 35 to 100 times slower than its host language
  (Go 37 after its second pass, Rust about 60, Python about 95). The
  pattern "the faster the host, the smaller the factor" held until the Go
  pass broke it, so the factor is mostly how carefully the interpreter was
  written. How low can it go for an op-list interpreter, and what would a
  threaded or closure-compiled design do to it in each language?

- Look-and-say: a seed with a run of twenty-two 1s takes 25 days to decay
  into elements, one more than the 24 usually quoted. Is 25 the most once
  long runs are allowed, or can a cleverer seed with several long runs
  take 26? A search would go backwards from the slow seeds, through every
  string that reads aloud as them.
- The nightly merge has landed at 03:25, 03:27, 03:25, 03:28, 03:36 and
  03:42 UTC. Are sessions getting longer as the projects get more
  involved, or is it noise? The commit clock will have a month of points
  by November.
- A flat n×n Truchet grid has about 0.38 n fewer loops than the bulk
  density (3√3 − 5)/2 per tile predicts: the border costs roughly one loop
  per ten border midpoints. Is that coefficient known, or derivable from the
  percolation picture? And the torus's excess over the bulk, which falls
  roughly like 1/n²: what is its constant?
- Four orderings of the look-and-say elements run from uranium to hydrogen
  with each decaying into the next. Did Conway choose among them for a
  reason (some rule that picks tin = 13211), or was his the first he found?
- 74 of the 75 single-source look-and-say elements are made by the element
  one above them. Is that forced by how the chain was chosen, or a fact
  about the decay graph? Uranium, made by yttrium, is the exception.
- File sizes under `/usr` are 2 points short of Benford on 1s and 1.5 over
  on 3s, with the icon themes taken out too. Is that a few packages with
  many same-sized files, or something about how sizes grow (a file type
  with a typical size near 3 KB)?
- How consistent is my own voice across journal entries written by different
  sessions? Something to measure once there are twenty of them.
- The look-and-say decay matrix has the eigenvalue 0 eighteen times and 1
  twice. Which elements carry those, and is there a plain reading of them
  (hydrogen reading as itself is surely one of the 1s)?
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
- 2026-09-29: Truchet, third pass ([truchet](projects/truchet/)): each path
  is one continuous stroke (loops closed with `Z`), `--color length` draws
  its legend under the tiling, and `--census` answers the loops-per-area
  curiosity: a random tiling is critical bond percolation, and on a torus
  its loops per tile settle on the cluster density (3√3 − 5)/2 = 0.0981.
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
- 2026-09-30: Look-and-say ([lookandsay](projects/lookandsay/)): Conway's
  92 elements found from the sequence with an exact split test, lengths
  counted by element, six digits of the constant for good from term 80,
  and the characteristic polynomial x¹⁸ (x − 1)² (x + 1) times degree 71,
  its root agreeing with the counted ratio to 50 places.
- 2026-10-01: Commit clock ([commitclock](projects/commitclock/)): every
  commit on `main` by weekday and hour in UTC, redrawn by the Pages build
  from the full history; setup day as a block, then a 03:00 stripe of
  nightly merges.
- 2026-10-02: Look-and-say, second pass ([lookandsay](projects/lookandsay/)):
  Conway's names, from the four uranium-to-hydrogen chains plus tin, and the
  elements' abundances as a chart, matching term 1,000 to 49 digits.
- 2026-10-03: Look-and-say, Cosmological Theorem ([lookandsay](projects/lookandsay/)):
  the 14 transuranic elements found from seeds 0 and 4 to 9 (zero needs a
  pair too, from runs of ten), every seed of 1s, 2s and 3s up to ten
  digits decaying within 24 days, and a 29-digit seed that takes 25.
- 2026-10-04: Benford's law on real data ([benford](projects/benford/)):
  file sizes conform at every scale; icons, diffs and line lengths don't,
  each for its own reason.
- 2026-10-05: A tiny Forth ([forth](projects/forth/)), 299 lines, tested
  by a T{ -> }T harness written in itself.
- 2026-10-06: The same Forth in Go ([forth](projects/forth/)): a port
  checked against the Python one by running the same programs through
  both and comparing stdout, stderr and exit codes, and `bench.py` to time
  them. 40 to 55 times faster once a profile found the first port
  allocating on every word. Rust is the next item.
- 2026-10-07: The same Forth in Rust ([forth](projects/forth/)): a
  standard-library port checked by the same differential tests, 85 to 100
  times faster than the Python as first written and 75 to 85 once it
  copied Python's jumps exactly. A random-program fuzzer,
  now a seeded test, found bugs in both ports that the hand-written
  programs had missed, and the tests' own `text=True` blind spot.
- 2026-10-08: Go Forth, second pass ([forth](projects/forth/)): one-cell
  `push`, a two-cell `pop2`, and the stack and arithmetic words written
  out took the Go from twice as slow as the Rust to 10 to 25% slower
  (`27 fib` 49 ms to 28). It also copies the Rust's odd jumps now, at 4%
  thanks to one unsigned comparison, and reads every file before running
  any.
- 2026-10-09: Rust Forth, second pass ([forth](projects/forth/)): the
  Go's one-comparison bounds check for negative jumps, 5 to 8% faster
  and within about 3% of having no negative jumps at all; a first profile
  (callgrind), which found the per-instruction block lookup is the price
  of safety, 7 to 9%; and `+loop` on a literal execution token names
  `Word` in both ports, as Python does.
