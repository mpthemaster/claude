"""Benford's law on real data: first digits of file sizes, diffs and line lengths.

Benford's law says that in many collections of numbers the leading digit d
turns up with probability log10(1 + 1/d): a 1 about 30% of the time, a 9
under 5%. This script gathers a few collections from the machine it runs on
and from this repository, counts their first digits, and measures how far
each is from the law, with the mean absolute deviation and Nigrini's
conformity ranges for it.

It also runs the test behind the law: multiply every number by the same
factor and count again. A collection that follows Benford's law keeps
following it at any scale; one that doesn't swings as the factor moves.

    python projects/benford/benford.py                  # the table
    python projects/benford/benford.py --sweep          # and the rescaling test
    python projects/benford/benford.py --out projects/benford/out
"""

from __future__ import annotations

import argparse
import math
import os
import stat
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path

DIGITS = range(1, 10)
BENFORD = tuple(math.log10(1 + 1 / d) for d in DIGITS)

# Nigrini's ranges for the first-digit mean absolute deviation: the upper
# bound of each verdict, from closest to furthest.
VERDICTS = (
    (0.006, "close conformity"),
    (0.012, "acceptable conformity"),
    (0.015, "marginal conformity"),
    (math.inf, "nonconformity"),
)

REPO = Path(__file__).resolve().parents[2]


def first_digit(x: float) -> int:
    """The leading nonzero digit of a positive number."""
    if x <= 0 or not math.isfinite(x):
        raise ValueError(f"no first digit for {x!r}")
    if isinstance(x, int):
        return int(str(x)[0])
    # Scientific notation puts the leading digit first, whatever the scale.
    return int(f"{x:e}"[0])


def digit_counts(values: Iterable[float]) -> list[int]:
    """How many of the positive values start with 1, 2, ..., 9.

    Zeros are skipped, since they have no first digit; negatives are an error.
    """
    counts = [0] * 9
    for x in values:
        if x == 0:
            continue
        counts[first_digit(x) - 1] += 1
    return counts


def proportions(counts: Sequence[int]) -> list[float]:
    total = sum(counts)
    if total == 0:
        raise ValueError("no values with a first digit")
    return [c / total for c in counts]


def mad(counts: Sequence[int]) -> float:
    """Mean absolute deviation of the digit proportions from Benford's."""
    return sum(abs(p - b) for p, b in zip(proportions(counts), BENFORD, strict=True)) / 9


def chi_square(counts: Sequence[int]) -> float:
    """Pearson's chi-square statistic against Benford's law (8 degrees of freedom).

    With tens of thousands of values it rejects any real collection, which is
    why the MAD, which doesn't grow with the sample, is the headline number.
    """
    total = sum(counts)
    return sum((c - total * b) ** 2 / (total * b) for c, b in zip(counts, BENFORD, strict=True))


def expected_mad(n: int) -> float:
    """The MAD a sample of n values drawn from Benford's law itself shows on average.

    Each proportion's error is roughly normal with variance b(1 - b) / n, and
    the mean absolute value of a normal is sqrt(2 / pi) times its spread.
    Nigrini's ranges assume this is negligible, which needs n in the thousands.
    """
    return sum(math.sqrt(2 * b * (1 - b) / (math.pi * n)) for b in BENFORD) / 9


def verdict(deviation: float) -> str:
    for bound, name in VERDICTS:
        if deviation <= bound:
            return name
    raise AssertionError("unreachable")  # pragma: no cover


def log_spread(values: Iterable[float]) -> float:
    """Standard deviation of log10 of the positive values: their width in decades."""
    logs = [math.log10(x) for x in values if x > 0]
    if not logs:
        raise ValueError("no positive values")
    mean = sum(logs) / len(logs)
    return math.sqrt(sum((v - mean) ** 2 for v in logs) / len(logs))


def scale_sweep(values: Sequence[float], steps: int = 40) -> list[tuple[float, float]]:
    """(factor, MAD) after multiplying every value by factors from 1 up to 10.

    The factors are evenly spaced on a log scale, 10 ** (k / steps), so the
    sweep covers every possible shift of the mantissas once.
    """
    positive = [x for x in values if x > 0]
    out = []
    for k in range(steps + 1):
        factor = 10 ** (k / steps)
        out.append((factor, mad(digit_counts(x * factor for x in positive))))
    return out


# --- gathering data ---------------------------------------------------------


def file_sizes(root: Path) -> list[int]:
    """The size in bytes of every regular file under root, symlinks not followed."""
    sizes = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            try:
                st = os.lstat(os.path.join(dirpath, name))
            except OSError:
                continue
            if stat.S_ISREG(st.st_mode):
                sizes.append(st.st_size)
    return sizes


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed in {repo}: {result.stderr.strip()}")
    return result.stdout


def line_lengths(repo: Path) -> list[int]:
    """The length of every nonempty line in every tracked text file."""
    lengths = []
    for name in _git(repo, "ls-files", "-z").split("\0"):
        if not name:
            continue
        try:
            text = (repo / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lengths.extend(len(line) for line in text.splitlines() if line)
    return lengths


def diff_sizes(repo: Path) -> list[int]:
    """Lines added and lines removed, per file per commit, across the history.

    Binary files, which git counts as "-", are left out. A shallow clone gives
    only the commits it has.
    """
    numbers = []
    for line in _git(repo, "log", "--numstat", "--format=").splitlines():
        for field in line.split("\t")[:2]:
            if field.isdigit():
                numbers.append(int(field))
    return numbers


@dataclass
class Dataset:
    name: str
    values: list[int]

    @property
    def counts(self) -> list[int]:
        return digit_counts(self.values)


SOURCES: dict[str, tuple[str, Callable[[], list[int]]]] = {
    "usr": ("file sizes under /usr", lambda: file_sizes(Path("/usr"))),
    "icons": ("icon sizes under /usr/share/icons", lambda: file_sizes(Path("/usr/share/icons"))),
    "diffs": ("lines changed per file per commit", lambda: diff_sizes(REPO)),
    "lines": ("line lengths in this repo", lambda: line_lengths(REPO)),
}


def gather(keys: Iterable[str]) -> list[Dataset]:
    out = []
    for key in keys:
        name, collect = SOURCES[key]
        values = [v for v in collect() if v > 0]
        if values:
            out.append(Dataset(name, values))
    return out


# --- text output ------------------------------------------------------------


def table(datasets: Sequence[Dataset]) -> str:
    head = f"{'':36} {'n':>7} " + " ".join(f"{d:>5}" for d in DIGITS)
    head += f" {'MAD':>7} {'noise':>7} {'decades':>7}  verdict"
    rows = [head, f"{'Benford':36} {'':>7} " + " ".join(f"{b:5.3f}" for b in BENFORD)]
    for ds in datasets:
        counts = ds.counts
        dev = mad(counts)
        rows.append(
            f"{ds.name:36} {sum(counts):7d} "
            + " ".join(f"{p:5.3f}" for p in proportions(counts))
            + f" {dev:7.4f} {expected_mad(sum(counts)):7.4f}"
            + f" {log_spread(ds.values):7.2f}  {verdict(dev)}"
        )
    return "\n".join(rows)


def sweep_table(datasets: Sequence[Dataset], steps: int = 40) -> str:
    rows = [f"{'':36} {'best MAD':>9} {'worst MAD':>9}  {'worst at':>8}"]
    for ds in datasets:
        sweep = scale_sweep(ds.values, steps)
        best = min(m for _, m in sweep)
        worst_factor, worst = max(sweep, key=lambda fm: fm[1])
        rows.append(f"{ds.name:36} {best:9.4f} {worst:9.4f}  ×{worst_factor:7.3f}")
    return "\n".join(rows)


# --- pictures ---------------------------------------------------------------

BAR = "#2a78d6"
SERIES = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100")
INK, MUTED, GRID, SURFACE = "#111", "#555", "#e5e5e5", "#fff"
FONT = "font-family='system-ui, -apple-system, Segoe UI, sans-serif'"


def digits_svg(datasets: Sequence[Dataset], columns: int = 2) -> str:
    """Small multiples: one panel per dataset, bars for its digits, dots for Benford's."""
    pw, ph = 360, 230  # panel size
    left, top, plot_w, plot_h = 44, 54, 300, 140
    ymax = 0.4
    rows = math.ceil(len(datasets) / columns)
    width, height = pw * columns + 20, ph * rows + 56
    out = [
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' "
        f"width='{width}' height='{height}' {FONT}>",
        f"<rect width='{width}' height='{height}' fill='{SURFACE}'/>",
        f"<text x='20' y='26' font-size='16' font-weight='600' fill='{INK}'>"
        "First digits against Benford's law</text>",
        f"<g transform='translate(20 40)'><rect x='0' y='-9' width='12' height='10' rx='2' "
        f"fill='{BAR}'/><text x='17' y='0' font-size='11' fill='{MUTED}'>observed</text>"
        f"<circle cx='88' cy='-4' r='4' fill='{INK}'/><text x='97' y='0' font-size='11' "
        f"fill='{MUTED}'>Benford, log₁₀(1 + 1/d)</text></g>",
    ]
    slot = plot_w / 9
    for i, ds in enumerate(datasets):
        ox = 10 + (i % columns) * pw
        oy = 50 + (i // columns) * ph
        counts = ds.counts
        props = proportions(counts)
        dev = mad(counts)
        out.append(f"<g transform='translate({ox} {oy})'>")
        out.append(
            f"<text x='{left}' y='22' font-size='13' font-weight='600' fill='{INK}'>"
            f"{escape(ds.name)}</text>"
        )
        out.append(
            f"<text x='{left}' y='38' font-size='11' fill='{MUTED}'>n = {sum(counts):,}, "
            f"MAD {dev:.4f}, {verdict(dev)}</text>"
        )
        for tick in (0, 0.1, 0.2, 0.3, 0.4):
            y = top + plot_h - tick / ymax * plot_h
            out.append(
                f"<line x1='{left}' x2='{left + plot_w}' y1='{y:.1f}' y2='{y:.1f}' "
                f"stroke='{GRID}'/>"
            )
            out.append(
                f"<text x='{left - 6}' y='{y + 4:.1f}' font-size='10' fill='{MUTED}' "
                f"text-anchor='end'>{tick:.0%}</text>"
            )
        points = []
        for d, p, b in zip(DIGITS, props, BENFORD, strict=True):
            x = left + (d - 1) * slot
            h = min(p, ymax) / ymax * plot_h
            y = top + plot_h - h
            bw = slot - 8
            # Rounded top, square base: a 4px-radius path anchored to the baseline.
            r = min(4, h, bw / 2)
            base = top + plot_h
            out.append(
                f"<path d='M{x + 4:.1f},{base} V{y + r:.1f} Q{x + 4:.1f},{y:.1f} "
                f"{x + 4 + r:.1f},{y:.1f} H{x + 4 + bw - r:.1f} Q{x + 4 + bw:.1f},{y:.1f} "
                f"{x + 4 + bw:.1f},{y + r:.1f} V{base}Z' fill='{BAR}'>"
                f"<title>{d}: {counts[d - 1]:,} values, {p:.1%} (Benford {b:.1%})</title></path>"
            )
            points.append((x + slot / 2, top + plot_h - b / ymax * plot_h))
            out.append(
                f"<text x='{x + slot / 2:.1f}' y='{base + 14}' font-size='11' "
                f"fill='{MUTED}' text-anchor='middle'>{d}</text>"
            )
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        out.append(f"<polyline points='{path}' fill='none' stroke='{INK}' stroke-width='1.5'/>")
        for (x, y), d, b in zip(points, DIGITS, BENFORD, strict=True):
            out.append(
                f"<circle cx='{x:.1f}' cy='{y:.1f}' r='4' fill='{INK}' stroke='{SURFACE}' "
                f"stroke-width='2'><title>Benford {d}: {b:.1%}</title></circle>"
            )
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def sweep_svg(datasets: Sequence[Dataset], steps: int = 40) -> str:
    """MAD against the rescaling factor, one line per dataset, thresholds shaded."""
    width, height = 800, 380
    left, top, plot_w, plot_h = 56, 64, 470, 260
    if len(datasets) > len(SERIES):
        raise ValueError(f"at most {len(SERIES)} lines on one chart")
    sweeps = [scale_sweep(ds.values, steps) for ds in datasets]
    ymax = max(0.02, max(m for s in sweeps for _, m in s))
    ymax = math.ceil(ymax * 100) / 100

    def sx(factor: float) -> float:
        return left + math.log10(factor) * plot_w

    def sy(m: float) -> float:
        return top + plot_h - m / ymax * plot_h

    out = [
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {width} {height}' "
        f"width='{width}' height='{height}' {FONT}>",
        f"<rect width='{width}' height='{height}' fill='{SURFACE}'/>",
        f"<text x='20' y='26' font-size='16' font-weight='600' fill='{INK}'>"
        "Distance from Benford's law as every value is rescaled</text>",
        f"<text x='20' y='44' font-size='11' fill='{MUTED}'>Mean absolute deviation "
        "after multiplying every value by the same factor. A collection that follows "
        "the law stays flat.</text>",
    ]
    tick = 0.01 if ymax <= 0.08 else 0.02
    t = 0.0
    while t <= ymax + 1e-9:
        y = sy(t)
        out.append(
            f"<line x1='{left}' x2='{left + plot_w}' y1='{y:.1f}' y2='{y:.1f}' stroke='{GRID}'/>"
        )
        out.append(
            f"<text x='{left - 6}' y='{y + 4:.1f}' font-size='10' fill='{MUTED}' "
            f"text-anchor='end'>{t:.2f}</text>"
        )
        t += tick
    # Nigrini's acceptable bound, dashed, labelled on the left inside the plot.
    y = sy(VERDICTS[1][0])
    out.append(
        f"<line x1='{left}' x2='{left + plot_w}' y1='{y:.1f}' y2='{y:.1f}' stroke='{MUTED}' "
        "stroke-dasharray='4 3'/>"
    )
    out.append(
        f"<text x='{left + 6}' y='{y - 5:.1f}' font-size='10' fill='{MUTED}'>"
        "acceptable conformity below 0.012</text>"
    )
    for f in (1, 2, 3, 5, 10):
        x = sx(f)
        out.append(
            f"<text x='{x:.1f}' y='{top + plot_h + 16}' font-size='10' fill='{MUTED}' "
            f"text-anchor='middle'>×{f}</text>"
        )
    out.append(
        f"<line x1='{left}' x2='{left + plot_w}' y1='{top + plot_h}' y2='{top + plot_h}' "
        f"stroke='{MUTED}'/>"
    )
    out.append(
        f"<text x='{left + plot_w / 2}' y='{top + plot_h + 34}' font-size='11' "
        f"fill='{MUTED}' text-anchor='middle'>scale factor (log axis)</text>"
    )
    # Direct labels at the right end, nudged apart so they never overlap.
    ends = sorted(((sy(s[-1][1]), i) for i, s in enumerate(sweeps)), key=lambda yi: yi[0])
    placed: list[tuple[float, int]] = []
    for y, i in ends:
        if placed and y - placed[-1][0] < 14:
            y = placed[-1][0] + 14
        placed.append((y, i))
    for s, ds, color in zip(sweeps, datasets, SERIES[: len(datasets)], strict=True):
        pts = " ".join(f"{sx(f):.1f},{sy(m):.1f}" for f, m in s)
        out.append(f"<polyline points='{pts}' fill='none' stroke='{color}' stroke-width='2'/>")
        for f, m in s:
            out.append(
                f"<circle cx='{sx(f):.1f}' cy='{sy(m):.1f}' r='6' fill='transparent'>"
                f"<title>{escape(ds.name)}, ×{f:.3f}: MAD {m:.4f}</title></circle>"
            )
    for y, i in placed:
        out.append(
            f"<rect x='{left + plot_w + 10}' y='{y - 5:.1f}' width='10' height='3' rx='1' "
            f"fill='{SERIES[i]}'/>"
            f"<text x='{left + plot_w + 25}' y='{y + 1:.1f}' font-size='11' fill='{INK}'>"
            f"{escape(datasets[i].name)}</text>"
        )
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "sources",
        nargs="*",
        metavar="SOURCE",
        help=f"which collections to study, from {', '.join(SOURCES)} (default: all)",
    )
    parser.add_argument("--sweep", action="store_true", help="also run the rescaling test")
    parser.add_argument("--out", type=Path, help="write digits.svg and sweep.svg here")
    args = parser.parse_args(argv)
    unknown = [s for s in args.sources if s not in SOURCES]
    if unknown:
        parser.error(f"unknown source {unknown[0]!r}; choose from {', '.join(SOURCES)}")
    datasets = gather(args.sources or SOURCES)
    if not datasets:
        print("no data found", file=sys.stderr)
        return 1
    print(table(datasets))
    if args.sweep:
        print()
        print(sweep_table(datasets))
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "digits.svg").write_text(digits_svg(datasets), encoding="utf-8")
        (args.out / "sweep.svg").write_text(sweep_svg(datasets), encoding="utf-8")
        print(f"\nwrote {args.out / 'digits.svg'} and {args.out / 'sweep.svg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
