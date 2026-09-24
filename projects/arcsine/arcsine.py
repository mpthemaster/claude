"""The arcsine law: how long a simple random walk spends on one side of zero.

A simple random walk takes steps of +1 or -1 with equal probability. Over a
long walk the fraction of time it spends on the positive side is not bunched
near one half, as intuition suggests. It follows the arcsine law, whose
density 1 / (pi * sqrt(x * (1 - x))) is largest at the two ends: a walk is
far more likely to spend nearly all its time on one side than to split its
time evenly. The same law governs the time of the last visit to zero.

Feller gives an exact version for a walk of 2n steps: the time on the
positive side is 2k with probability u(k) * u(n - k), where
u(k) = C(2k, k) / 4^k is the probability of being back at zero after 2k
steps, and the last zero is at time 2k with the same probability.

This module simulates many walks, measures three things about each (the time
on the positive side, the last zero, and the longest stretch away from zero),
compares the first two with Feller's law and the third with a renewal
recursion, and draws the comparison as an SVG.

Usage:
    python arcsine.py                              # simulate, print a summary
    python arcsine.py --out out/arcsine.svg        # and write the chart
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from bisect import bisect_right
from collections.abc import Iterable, Sequence
from fractions import Fraction
from itertools import accumulate
from math import comb
from pathlib import Path
from typing import NamedTuple

STEP = {"0": -1, "1": 1}


class Measure(NamedTuple):
    """Three things measured on one walk of m steps.

    positive_time: time units spent on the positive side, in Feller's sense:
        the interval (k-1, k) counts if S_{k-1} > 0 or S_k > 0. Always even.
    last_zero: the last time the walk is at zero (0 if it never returns).
    longest_excursion: the longest stretch that never touches zero, counting
        the unfinished stretch after the last zero.
    """

    positive_time: int
    last_zero: int
    longest_excursion: int


# --- walks and measurements -------------------------------------------------


def random_walk(rng: random.Random, steps: int) -> list[int]:
    """Positions S_0, ..., S_steps of a simple random walk starting at 0."""
    if steps < 0:
        raise ValueError("steps must not be negative")
    bits = format(rng.getrandbits(steps), f"0{steps}b") if steps else ""
    walk = [0]
    walk.extend(accumulate(STEP[b] for b in bits))
    return walk


def zeros_of(walk: Sequence[int]) -> list[int]:
    """Indices where the walk is at zero, in order. The first is always 0."""
    found = []
    i = 0
    while True:
        try:
            i = walk.index(0, i)
        except ValueError:
            return found
        found.append(i)
        i += 1


def measure(walk: Sequence[int]) -> Measure:
    """Measure a walk given as positions S_0 = 0, S_1, ..., S_m."""
    if not walk or walk[0] != 0:
        raise ValueError("a walk starts at zero")
    zeros = zeros_of(walk)
    # Count the k with S_k > 0, then add the intervals that end at zero coming
    # down from 1: those have S_{k-1} > 0 but were not counted.
    positives = sum(map((0).__lt__, walk))
    from_above = sum(1 for z in zeros if z > 0 and walk[z - 1] == 1)
    stretches = [b - a for a, b in zip(zeros, zeros[1:], strict=False)]
    stretches.append(len(walk) - 1 - zeros[-1])
    return Measure(positives + from_above, zeros[-1], max(stretches))


def simulate(steps: int, walks: int, seed: int) -> list[Measure]:
    """Measure `walks` independent walks of `steps` steps each, from one seed."""
    if steps <= 0 or steps % 2:
        raise ValueError("steps must be a positive even number")
    if walks <= 0:
        raise ValueError("walks must be positive")
    rng = random.Random(seed)
    return [measure(random_walk(rng, steps)) for _ in range(walks)]


# --- the exact laws -------------------------------------------------------------


def u(k: int) -> Fraction:
    """Probability that a walk is back at zero after 2k steps: C(2k, k) / 4^k."""
    return Fraction(comb(2 * k, k), 4**k)


def return_probabilities(n: int, exact: bool) -> list:
    """u(0), ..., u(n), as Fractions or as floats."""
    us = [u(k) for k in range(n + 1)]
    return us if exact else [float(x) for x in us]


def exact_law(n: int) -> list[Fraction]:
    """Feller's discrete arcsine law for a walk of 2n steps.

    Entry k is the probability that the time on the positive side is 2k, and
    also the probability that the last zero is at time 2k: u(k) * u(n - k).
    """
    us = return_probabilities(n, exact=True)
    return [us[k] * us[n - k] for k in range(n + 1)]


def arcsine_cdf(x: float) -> float:
    """The limit law: the probability that the fraction is at most x."""
    return 2 / math.pi * math.asin(math.sqrt(x))


def longest_excursion_cdf(steps: int, max_len: int, exact: bool = False):
    """Probability that no stretch away from zero is longer than max_len.

    Every stretch of an even-length walk has even length (zeros sit at even
    times), so an odd max_len is the same as the even number below it. The
    recursion is over returns to zero: g[t] is the probability of being at
    zero at time 2t with every completed stretch at most max_len long, built
    from the first-return probabilities f(j) = u(j-1) - u(j). The walk then
    ends with an unfinished stretch of 2(n-t) steps, which must also be short
    enough, and has probability u(n-t) of not touching zero.
    """
    if steps <= 0 or steps % 2:
        raise ValueError("steps must be a positive even number")
    n = steps // 2
    if max_len < 0:
        return Fraction(0) if exact else 0.0
    limit = min(max_len // 2, n)
    us = return_probabilities(n, exact)
    first_return = [None] + [us[j - 1] - us[j] for j in range(1, n + 1)]
    g = _short_excursion_returns(first_return, limit, n)
    return sum(g[t] * us[n - t] for t in range(n - limit, n + 1))


def _short_excursion_returns(first_return, limit: int, t: int) -> list:
    """g[0..t]: probability of being at zero at time 2s with every completed
    stretch so far at most 2 * limit long."""
    g = [first_return[1] * 0 + 1] + [first_return[1] * 0] * t
    for s in range(1, t + 1):
        g[s] = sum(first_return[j] * g[s - j] for j in range(1, min(limit, s) + 1))
    return g


def final_stretch_is_longest(steps: int, exact: bool = False):
    """Probability that the unfinished stretch after the last zero is at
    least as long as every completed excursion. Cubic in the number of
    steps, so meant for a few hundred steps at most."""
    if steps <= 0 or steps % 2:
        raise ValueError("steps must be a positive even number")
    n = steps // 2
    us = return_probabilities(n, exact)
    first_return = [None] + [us[j - 1] - us[j] for j in range(1, n + 1)]
    total = 0 * us[0]
    for t in range(n + 1):
        g = _short_excursion_returns(first_return, n - t, t)
        total += g[t] * us[n - t]
    return total


def mean_longest_excursion(steps: int, exact: bool = False):
    """Expected length of the longest excursion, in steps. Cubic in the
    number of steps, so meant for a few hundred steps at most."""
    if steps <= 0 or steps % 2:
        raise ValueError("steps must be a positive even number")
    n = steps // 2
    one = Fraction(1) if exact else 1.0
    # Every length is even, so E[L] = 2 * sum over l of P(L > 2l).
    return 2 * sum(one - longest_excursion_cdf(steps, 2 * lo, exact) for lo in range(n))


# --- binning ----------------------------------------------------------------------


def bin_edges(steps: int, bins: int) -> list[int]:
    """Lower edges, in time units, of `bins` equal bins over 0..steps."""
    if bins <= 0:
        raise ValueError("bins must be positive")
    return [b * steps // bins for b in range(bins)]


def bin_of(value: int, edges: Sequence[int]) -> int:
    return bisect_right(edges, value) - 1


def histogram(values: Iterable[int], edges: Sequence[int]) -> list[float]:
    """Share of the values falling in each bin."""
    counts = [0] * len(edges)
    total = 0
    for v in values:
        counts[bin_of(v, edges)] += 1
        total += 1
    return [c / total for c in counts]


def binned_exact_law(steps: int, edges: Sequence[int]) -> list[float]:
    """Feller's law for `steps` steps, as probability per bin."""
    masses = [0.0] * len(edges)
    for k, p in enumerate(exact_law(steps // 2)):
        masses[bin_of(2 * k, edges)] += float(p)
    return masses


def binned_arcsine_law(steps: int, edges: Sequence[int]) -> list[float]:
    """The limit law, as probability per bin."""
    uppers = [*edges[1:], steps]
    return [
        arcsine_cdf(hi / steps) - arcsine_cdf(lo / steps)
        for lo, hi in zip(edges, uppers, strict=True)
    ]


def binned_longest_excursion_law(steps: int, edges: Sequence[int]) -> list[float]:
    """The exact law of the longest excursion, as probability per bin."""
    uppers = [*(e - 1 for e in edges[1:]), steps]
    cdf_at = {}
    for x in {*(e - 1 for e in edges), *uppers}:
        cdf_at[x] = 1.0 if x >= steps else longest_excursion_cdf(steps, x)
    return [cdf_at[hi] - cdf_at[lo - 1] for lo, hi in zip(edges, uppers, strict=True)]


# --- summary ---------------------------------------------------------------------------


def ks_distance(values: Sequence[int], law: Sequence, steps: int) -> float:
    """Largest gap between the empirical distribution and Feller's law."""
    ordered = sorted(values)
    total = len(ordered)
    worst = 0.0
    cdf = 0.0
    for k, p in enumerate(law):
        cdf += float(p)
        empirical = bisect_right(ordered, 2 * k) / total
        worst = max(worst, abs(empirical - cdf))
    return worst


def report(steps: int, results: Sequence[Measure], bins: int = 20) -> list[str]:
    """Plain-text summary: the headline numbers, then one row per bin."""
    n = len(results)
    edges = bin_edges(steps, bins)
    law = exact_law(steps // 2)
    positive = [r.positive_time for r in results]
    last = [r.last_zero for r in results]
    longest = [r.longest_excursion for r in results]
    one_sided = sum(1 for p in positive if p <= steps / 10 or p >= steps * 9 / 10) / n
    even = sum(1 for p in positive if steps * 2 / 5 <= p <= steps * 3 / 5) / n
    exact_one_sided = float(sum(p for k, p in enumerate(law) if 2 * k <= steps / 10)) * 2
    exact_even = float(sum(p for k, p in enumerate(law) if steps * 2 / 5 <= 2 * k <= steps * 3 / 5))
    final_is_longest = sum(1 for r in results if steps - r.last_zero == r.longest_excursion) / n
    lines = [
        f"{n} walks of {steps} steps",
        f"positive side, mean fraction: {sum(positive) / n / steps:.4f}"
        f"  (KS distance from the exact law {ks_distance(positive, law, steps):.4f})",
        f"last zero, mean fraction:     {sum(last) / n / steps:.4f}"
        f"  (KS distance from the exact law {ks_distance(last, law, steps):.4f})",
        f"longest excursion, mean fraction: {sum(longest) / n / steps:.4f}",
        f"walks at least 90% on one side: {one_sided:.4f}  (exact {exact_one_sided:.4f})",
        f"walks between 40% and 60% positive: {even:.4f}  (exact {exact_even:.4f})",
        f"walks whose final stretch is the longest: {final_is_longest:.4f}",
        "",
        "bin      positive   exact   last zero   exact   longest   exact   arcsine",
    ]
    rows = zip(
        edges,
        histogram(positive, edges),
        histogram(last, edges),
        binned_exact_law(steps, edges),
        histogram(longest, edges),
        binned_longest_excursion_law(steps, edges),
        binned_arcsine_law(steps, edges),
        strict=True,
    )
    for lo, sim_positive, sim_last, feller, sim_longest, longest_law, arcsine in rows:
        lines.append(
            f"{lo / steps:.2f}     {sim_positive:.4f}    {feller:.4f}   {sim_last:.4f}     "
            f"{feller:.4f}   {sim_longest:.4f}    {longest_law:.4f}   {arcsine:.4f}"
        )
    return lines


# --- the chart -------------------------------------------------------------------------

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e6e5e1"
PATH = "#a3a29c"


def _num(x: float) -> str:
    return f"{x:.1f}".rstrip("0").rstrip(".")


def positive_pieces(walk: Sequence[int]) -> list[tuple[int, int]]:
    """Index ranges (a, b) of the path above zero, including the zeros at each end."""
    pieces = []
    m = len(walk) - 1
    i = 1
    while i <= m:
        if walk[i] > 0:
            start = i - 1
            while i <= m and walk[i] > 0:
                i += 1
            pieces.append((start, min(i, m)))
        else:
            i += 1
    return pieces


def _walk_panel(
    walk: Sequence[int], x0: float, y0: float, width: float, height: float
) -> list[str]:
    m = len(walk) - 1
    found = measure(walk)
    zeros = zeros_of(walk)
    stretches = [(a, b) for a, b in zip(zeros, zeros[1:], strict=False)] + [(zeros[-1], m)]
    longest = max(stretches, key=lambda s: s[1] - s[0])
    top, bottom = y0 + 18, y0 + height - 30
    mid = (top + bottom) / 2
    scale = (bottom - top) / 2 / max(abs(min(walk)), abs(max(walk)), 1)

    def x(i: int) -> float:
        return x0 + i * width / m

    def y(v: int) -> float:
        return mid - v * scale

    def polyline(a: int, b: int, color: str, stroke_width: float) -> str:
        points = " ".join(f"{_num(x(i))},{_num(y(walk[i]))}" for i in range(a, b + 1))
        return (
            f'<polyline points="{points}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_width}" stroke-linejoin="round"/>'
        )

    out = [
        f'<text x="{_num(x0)}" y="{_num(y0)}" font-size="13" font-weight="600" fill="{INK}">'
        f"One walk of {m:,} steps: on the positive side for "
        f"{found.positive_time / m:.0%} of the time, last at zero at step "
        f"{found.last_zero:,}, longest stretch away from zero {found.longest_excursion:,} steps"
        "</text>",
        f'<line x1="{_num(x0)}" y1="{_num(mid)}" x2="{_num(x0 + width)}" y2="{_num(mid)}" '
        f'stroke="{GRID}" stroke-width="1"/>',
        polyline(0, m, PATH, 1.2),
    ]
    out.extend(polyline(a, b, BLUE, 1.6) for a, b in positive_pieces(walk))
    lz = x(found.last_zero)
    out.append(
        f'<line x1="{_num(lz)}" y1="{_num(mid)}" x2="{_num(lz)}" y2="{_num(bottom + 6)}" '
        f'stroke="{INK}" stroke-width="1"/>'
    )
    anchor = "end" if found.last_zero > m / 2 else "start"
    dx = -4 if anchor == "end" else 4
    out.append(
        f'<text x="{_num(lz + dx)}" y="{_num(bottom + 4)}" font-size="11" fill="{MUTED}" '
        f'text-anchor="{anchor}">last zero</text>'
    )
    xa, xb = x(longest[0]), x(longest[1])
    yb = bottom + 16
    out.append(
        f'<path d="M{_num(xa)},{_num(yb - 4)} V{_num(yb)} H{_num(xb)} V{_num(yb - 4)}" '
        f'fill="none" stroke="{ORANGE}" stroke-width="1.5"/>'
    )
    out.append(
        f'<text x="{_num((xa + xb) / 2)}" y="{_num(yb + 11)}" font-size="11" fill="{MUTED}" '
        f'text-anchor="middle">longest excursion</text>'
    )
    return out


def _histogram_panel(
    title: str,
    simulated: Sequence[float],
    exact: Sequence[float],
    limit: Sequence[float] | None,
    x0: float,
    y0: float,
    width: float,
    height: float,
    ymax: float,
) -> list[str]:
    bins = len(simulated)
    top, bottom = y0 + 22, y0 + height - 24
    slot = width / bins

    def y(v: float) -> float:
        return bottom - v / ymax * (bottom - top)

    out = [
        f'<text x="{_num(x0)}" y="{_num(y0 + 6)}" font-size="13" font-weight="600" '
        f'fill="{INK}">{title}</text>'
    ]
    tick = 0.05
    while tick <= ymax + 1e-9:
        yy = y(tick)
        out.append(
            f'<line x1="{_num(x0)}" y1="{_num(yy)}" x2="{_num(x0 + width)}" y2="{_num(yy)}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{_num(x0 - 6)}" y="{_num(yy + 4)}" font-size="11" fill="{MUTED}" '
            f'text-anchor="end">{tick:.2f}</text>'
        )
        tick += 0.05
    for b, share in enumerate(simulated):
        xl = x0 + b * slot + 1
        out.append(
            f'<rect x="{_num(xl)}" y="{_num(y(share))}" width="{_num(slot - 2)}" '
            f'height="{_num(bottom - y(share))}" fill="{BLUE}"/>'
        )
    if limit is not None:
        points = []
        for b, mass in enumerate(limit):
            points.append(f"{_num(x0 + b * slot)},{_num(y(mass))}")
            points.append(f"{_num(x0 + (b + 1) * slot)},{_num(y(mass))}")
        out.append(
            f'<polyline points="{" ".join(points)}" fill="none" stroke="{ORANGE}" '
            f'stroke-width="2"/>'
        )
    for b, mass in enumerate(exact):
        out.append(
            f'<circle cx="{_num(x0 + (b + 0.5) * slot)}" cy="{_num(y(mass))}" r="2.5" '
            f'fill="{INK}"/>'
        )
    out.append(
        f'<line x1="{_num(x0)}" y1="{_num(bottom)}" x2="{_num(x0 + width)}" y2="{_num(bottom)}" '
        f'stroke="{MUTED}" stroke-width="1"/>'
    )
    for frac, label in ((0, "0"), (0.25, "0.25"), (0.5, "0.5"), (0.75, "0.75"), (1, "1")):
        xx = x0 + frac * width
        out.append(
            f'<text x="{_num(xx)}" y="{_num(bottom + 15)}" font-size="11" fill="{MUTED}" '
            f'text-anchor="middle">{label}</text>'
        )
    return out


def render_svg(
    steps: int,
    results: Sequence[Measure],
    bins: int = 20,
    walk: Sequence[int] | None = None,
) -> str:
    """The chart: one sample walk on top, then three histograms with their laws."""
    edges = bin_edges(steps, bins)
    exact = binned_exact_law(steps, edges)
    limit = binned_arcsine_law(steps, edges)
    longest_law = binned_longest_excursion_law(steps, edges)
    panels = [
        ("Time on the positive side", histogram((r.positive_time for r in results), edges), exact),
        ("Time of the last zero", histogram((r.last_zero for r in results), edges), exact),
        ("Longest excursion", histogram((r.longest_excursion for r in results), edges), None),
    ]
    ymax = max(max(s) for _, s, _ in panels)
    ymax = max(ymax, max(exact), max(limit), max(longest_law))
    ymax = math.ceil(ymax / 0.05 + 0.2) * 0.05

    width, margin, gap = 960, 36, 30
    # The walk panel's labels end 3px above its nominal bottom; the legend
    # row goes under them, then the histograms.
    walk_height = 150 if walk is not None else 0
    hist_top = 70 + (walk_height + 38 if walk is not None else 0)
    hist_height = 230
    height = hist_top + hist_height + 8
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="12">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{margin}" y="28" font-size="17" font-weight="600" fill="{INK}">'
        "How long does a random walk spend on one side of zero?</text>",
        f'<text x="{margin}" y="46" fill="{MUTED}">{len(results):,} simple random walks of '
        f"{steps:,} steps. Across: the fraction of the walk. Up: the share of walks in "
        f"each bin of {1 / bins:g}.</text>",
    ]
    if walk is not None:
        out.extend(_walk_panel(walk, margin, 72, width - 2 * margin, walk_height))
    panel_width = (width - 2 * margin - 2 * gap) / 3
    laws = (limit, limit, None)
    for i, ((title, simulated, law), limit_law) in enumerate(zip(panels, laws, strict=True)):
        x0 = margin + i * (panel_width + gap)
        out.extend(
            _histogram_panel(
                title,
                simulated,
                law if law is not None else longest_law,
                limit_law,
                x0,
                hist_top,
                panel_width,
                hist_height,
                ymax,
            )
        )
    legend_y = hist_top - 14
    lx = width - margin
    items = [
        (
            f'<line x1="0" y1="0" x2="18" y2="0" stroke="{ORANGE}" stroke-width="2"/>',
            18,
            "arcsine law (limit)",
        ),
        (f'<circle cx="3" cy="0" r="2.5" fill="{INK}"/>', 6, f"exact law for {steps:,} steps"),
        (f'<rect x="0" y="-5" width="10" height="10" fill="{BLUE}"/>', 10, "simulated"),
    ]
    for mark, mark_width, label in items:
        lx -= len(label) * 6.2
        out.append(
            f'<text x="{_num(lx)}" y="{_num(legend_y + 4)}" font-size="11" fill="{MUTED}">'
            f"{label}</text>"
        )
        lx -= mark_width + 6
        out.append(f'<g transform="translate({_num(lx)},{_num(legend_y)})">{mark}</g>')
        lx -= 18
    out.append("</svg>")
    return "\n".join(out) + "\n"


# --- CLI -----------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Random walks against the arcsine law.")
    parser.add_argument("--steps", type=int, default=1000, help="steps per walk (even)")
    parser.add_argument("--walks", type=int, default=20000, help="number of walks")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--bins", type=int, default=20)
    parser.add_argument("--out", type=Path, help="write the SVG chart here")
    parser.add_argument(
        "--exact-longest",
        action="store_true",
        help="print the exact mean longest excursion and the chance the final stretch is the "
        "longest, for --steps steps, instead of simulating (cubic time, fine up to a few hundred)",
    )
    args = parser.parse_args(argv)
    if args.exact_longest:
        try:
            mean = mean_longest_excursion(args.steps)
            final = final_stretch_is_longest(args.steps)
        except ValueError as err:
            print(f"error: {err}", file=sys.stderr)
            return 2
        print(f"walks of {args.steps} steps, exactly:")
        print(f"longest excursion, mean fraction: {mean / args.steps:.6f}")
        print(f"walks whose final stretch is the longest: {final:.6f}")
        return 0
    try:
        results = simulate(args.steps, args.walks, args.seed)
        lines = report(args.steps, results, args.bins)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    if args.out:
        # The sample walk is the first one the seed produces.
        walk = random_walk(random.Random(args.seed), args.steps)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_svg(args.steps, results, args.bins, walk), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
