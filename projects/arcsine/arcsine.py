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
steps, and the last zero is at time 2k with the same probability. The time
of the walk's first maximum has the same limit and a slightly different
exact law: u(k // 2) * u(n - k // 2) / 2 at each time k >= 1, and u(n) at
time 0.

This module simulates many walks, measures four things about each (the time
on the positive side, the last zero, the first maximum, and the longest
stretch away from zero), compares the first three with Feller's laws and the
fourth with a renewal recursion, and draws the comparison as an SVG. The
same recursion gives the exact mean of the longest excursion and the chance
that the unfinished final stretch is the longest, at every length up to the
one asked for.

Usage:
    python arcsine.py                              # simulate, print a summary
    python arcsine.py --out out/arcsine.svg        # and write the chart
    python arcsine.py --exact-longest              # the longest excursion, exactly
    python arcsine.py --exact-longest --out out/longest.svg   # and its chart
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
from operator import mul
from pathlib import Path
from typing import NamedTuple

STEP = {"0": -1, "1": 1}


class Measure(NamedTuple):
    """Four things measured on one walk of m steps.

    positive_time: time units spent on the positive side, in Feller's sense:
        the interval (k-1, k) counts if S_{k-1} > 0 or S_k > 0. Always even.
    last_zero: the last time the walk is at zero (0 if it never returns).
    first_max: the first time the walk is at its maximum (0 if it never
        rises above its start).
    longest_excursion: the longest stretch that never touches zero, counting
        the unfinished stretch after the last zero.
    """

    positive_time: int
    last_zero: int
    first_max: int
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
    return Measure(positives + from_above, zeros[-1], walk.index(max(walk)), max(stretches))


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


def first_max_law(n: int) -> list[Fraction]:
    """Feller's law for the time of the first maximum of a walk of 2n steps.

    Entry k is the probability that the walk is first at its maximum at time
    k. The k steps before that time, read backwards, are a walk that stays
    strictly positive, which happens with probability u(k // 2) / 2 for
    k >= 1; the steps after it are a walk that stays at or below zero, with
    probability u(m) for 2m or 2m - 1 steps. So the time is 0 with
    probability u(n), and k >= 1 with probability u(j) u(n - j) / 2 where
    j = k // 2. Times 2j and 2j + 1 together carry the arcsine law's atom
    u(j) u(n - j), except at the two ends: the atom at 0 is whole and time
    1 carries another half of it, while the atom at 2n is halved, which
    pays for that since the two end atoms are equal. The tie between equal
    maxima goes to the earlier one: a walk that never rises above zero has
    its first maximum at time 0 whatever it does later, while a maximum at
    the last step has to be strict.
    """
    us = return_probabilities(n, exact=True)
    law = [us[n]]
    law.extend(us[k // 2] * us[n - k // 2] / 2 for k in range(1, 2 * n + 1))
    return law


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
    g = _short_excursion_returns(us, limit, n)
    return sum(g[t] * us[n - t] for t in range(n - limit, n + 1))


def _short_excursion_returns(us, limit: int, t: int) -> list:
    """g[0..t]: probability of being at zero at time 2s with every completed
    stretch so far at most 2 * limit long, given u(0), ..., u(t).

    Up to s = limit no stretch can be too long, so g[s] = u(s). Up to
    s = 2 * limit at most one can, and a bridge of 2s steps holds one of
    length 2j with probability f(j) whatever happens around it, so the too
    long ones together weigh u(limit) - u(s) and g[s] = 2 u(s) - u(limit).
    From there the renewal recursion g[s] = sum of f(j) g[s - j] over
    j <= limit takes over, each step a dot product of the last `limit`
    values with the first-return probabilities. That costs limit * (t - 2
    * limit) multiplications for a row, and nothing for a row whose t is
    within twice its limit.
    """
    g = list(us[: min(limit, t) + 1])
    g.extend(2 * us[s] - us[limit] for s in range(limit + 1, min(2 * limit, t) + 1))
    if t > 2 * limit:
        first_return = [us[j - 1] - us[j] for j in range(limit, 0, -1)]
        for s in range(2 * limit + 1, t + 1):
            g.append(sum(map(mul, first_return, g[s - limit : s])))
    return g


def final_stretch_probabilities(steps: int, exact: bool = False) -> list:
    """For walks of 0, 2, ..., `steps` steps in turn, the probability that
    the unfinished stretch after the last zero is at least as long as every
    completed excursion.

    A walk of 2k steps whose last zero is at 2t ends with a stretch of
    2(k - t) steps, which stays away from zero with probability u(k - t),
    and the bridge before it must have no excursion longer than that: the
    probability is the sum over t of g[t] u(k - t) with g the row of
    `_short_excursion_returns` for limit k - t. Row `limit` serves every k
    at once, as far as t = n - limit, so one pass over the rows gives every
    length up to `steps`. The work is about (steps / 2)^3 / 54
    multiplications, in C: a fifth of a second for 1,000 steps and about
    six for 4,000.
    """
    if steps <= 0 or steps % 2:
        raise ValueError("steps must be a positive even number")
    n = steps // 2
    us = return_probabilities(n, exact)
    probabilities = [0 * us[0]] * (n + 1)
    for limit in range(n + 1):
        for t, g in enumerate(_short_excursion_returns(us, limit, n - limit)):
            probabilities[limit + t] += g * us[limit]
    return probabilities


def mean_longest_excursions(steps: int, exact: bool = False) -> list:
    """Expected length of the longest excursion, in steps, for walks of
    0, 2, ..., `steps` steps in turn.

    Two more steps lengthen the longest excursion by exactly two when the
    final stretch was already at least as long as every completed
    excursion, and not at all otherwise: whether or not the walk is back
    at zero at the new end, the new longest is the larger of the longest
    completed excursion and the old final stretch plus two. So the mean
    grows by twice the probability in `final_stretch_probabilities` at each
    length, and the means are running sums of those.
    """
    return means_from_probabilities(final_stretch_probabilities(steps, exact))


def means_from_probabilities(probabilities: Sequence) -> list:
    """The means of `mean_longest_excursions` from the table of
    `final_stretch_probabilities`, so a table already in hand isn't built
    twice: twice the running sums, starting from a walk of no steps."""
    return [2 * s for s in accumulate(probabilities[:-1], initial=0 * probabilities[0])]


def final_stretch_is_longest(steps: int, exact: bool = False):
    """Probability that the unfinished stretch after the last zero is at
    least as long as every completed excursion."""
    return final_stretch_probabilities(steps, exact)[-1]


def mean_longest_excursion(steps: int, exact: bool = False):
    """Expected length of the longest excursion, in steps."""
    return mean_longest_excursions(steps, exact)[-1]


def longest_excursion_limit(intervals: int = 20000) -> float:
    """The limit, as the walk grows, of the chance that the final stretch is
    the longest, which is also the limit of the mean longest excursion as a
    fraction of the walk: the integral over a > 0 of
    1 / (1 + sqrt(pi a) e^a erf(sqrt a)), by Simpson's rule.

    The integral is Brownian motion's version of the renewal sum in
    `final_stretch_probabilities`, stopped at an exponential time (the
    README derives it). The integrand is smooth, starts at 1 and falls like
    e^-a / sqrt(pi a), so [0, 40] holds all of it that a float can see.
    """
    if intervals <= 0 or intervals % 2:
        raise ValueError("intervals must be a positive even number")

    def f(a: float) -> float:
        root = math.sqrt(a)
        return 1 / (1 + math.sqrt(math.pi) * root * math.exp(a) * math.erf(root))

    h = 40 / intervals
    inner = sum((4 if i % 2 else 2) * f(i * h) for i in range(1, intervals))
    return (f(0) + inner + f(40)) * h / 3


# --- binning ----------------------------------------------------------------------


def bin_edges(steps: int, bins: int) -> list[int]:
    """Lower edges, in time units, of `bins` equal bins over 0..steps.

    The bins are drawn and described as equal, so they have to be: the
    number of bins must divide the number of steps.
    """
    if bins <= 0:
        raise ValueError("bins must be positive")
    if steps % bins:
        raise ValueError("bins must divide the number of steps")
    return [b * (steps // bins) for b in range(bins)]


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


def binned_first_max_law(steps: int, edges: Sequence[int]) -> list[float]:
    """Feller's law for the first maximum of `steps` steps, as probability per bin."""
    masses = [0.0] * len(edges)
    for k, p in enumerate(first_max_law(steps // 2)):
        masses[bin_of(k, edges)] += float(p)
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


def ks_distance(values: Sequence[int], law: Sequence, spacing: int) -> float:
    """Largest gap between the empirical distribution of the values and an
    exact law whose entry k is the probability of the value k * spacing."""
    ordered = sorted(values)
    total = len(ordered)
    worst = 0.0
    cdf = 0.0
    for k, p in enumerate(law):
        cdf += float(p)
        empirical = bisect_right(ordered, k * spacing) / total
        worst = max(worst, abs(empirical - cdf))
    return worst


def report(steps: int, results: Sequence[Measure], bins: int = 20) -> list[str]:
    """Plain-text summary: the headline numbers, then one row per bin."""
    n = len(results)
    edges = bin_edges(steps, bins)
    law = exact_law(steps // 2)
    max_law = first_max_law(steps // 2)
    positive = [r.positive_time for r in results]
    last = [r.last_zero for r in results]
    first_max = [r.first_max for r in results]
    longest = [r.longest_excursion for r in results]
    one_sided = sum(1 for p in positive if p <= steps / 10 or p >= steps * 9 / 10) / n
    even = sum(1 for p in positive if steps * 2 / 5 <= p <= steps * 3 / 5) / n
    exact_one_sided = float(sum(p for k, p in enumerate(law) if 2 * k <= steps / 10)) * 2
    exact_even = float(sum(p for k, p in enumerate(law) if steps * 2 / 5 <= 2 * k <= steps * 3 / 5))
    early = sum(1 for t in first_max if t <= steps / 10) / n
    late = sum(1 for t in first_max if t >= steps * 9 / 10) / n
    exact_early = float(sum(p for k, p in enumerate(max_law) if k <= steps / 10))
    exact_late = float(sum(p for k, p in enumerate(max_law) if k >= steps * 9 / 10))
    exact_mean_max = float(sum(k * p for k, p in enumerate(max_law))) / steps
    final_is_longest = sum(1 for r in results if steps - r.last_zero == r.longest_excursion) / n
    lines = [
        f"{n} walks of {steps} steps",
        f"positive side, mean fraction:     {sum(positive) / n / steps:.4f}"
        f"  (KS distance from the exact law {ks_distance(positive, law, 2):.4f})",
        f"last zero, mean fraction:         {sum(last) / n / steps:.4f}"
        f"  (KS distance from the exact law {ks_distance(last, law, 2):.4f})",
        f"first maximum, mean fraction:     {sum(first_max) / n / steps:.4f}"
        f"  (KS distance from the exact law {ks_distance(first_max, max_law, 1):.4f}; "
        f"exact mean {exact_mean_max:.4f})",
        f"longest excursion, mean fraction: {sum(longest) / n / steps:.4f}",
        f"walks at least 90% on one side: {one_sided:.4f}  (exact {exact_one_sided:.4f})",
        f"walks between 40% and 60% positive: {even:.4f}  (exact {exact_even:.4f})",
        f"walks whose maximum comes in the first tenth: {early:.4f}  (exact {exact_early:.4f}),"
        f" in the last tenth: {late:.4f}  (exact {exact_late:.4f})",
        f"walks whose final stretch is the longest: {final_is_longest:.4f}",
        "",
    ]
    columns = [
        ("positive", histogram(positive, edges)),
        ("exact", binned_exact_law(steps, edges)),
        ("last zero", histogram(last, edges)),
        ("exact", binned_exact_law(steps, edges)),
        ("first max", histogram(first_max, edges)),
        ("exact", binned_first_max_law(steps, edges)),
        ("longest", histogram(longest, edges)),
        ("exact", binned_longest_excursion_law(steps, edges)),
        ("arcsine", binned_arcsine_law(steps, edges)),
    ]
    lines.append("bin   " + "  ".join(f"{name:>9}" for name, _ in columns))
    for b, lo in enumerate(edges):
        lines.append(
            f"{lo / steps:.2f}  " + "  ".join(f"{values[b]:9.4f}" for _, values in columns)
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
        f"One walk of {m:,} steps: {found.positive_time / m:.0%} on the positive side, "
        f"highest at step {found.first_max:,}, last at zero at step {found.last_zero:,}, "
        f"longest stretch away from zero {found.longest_excursion:,} steps"
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
    peak_x, peak_y = x(found.first_max), y(walk[found.first_max])
    out.append(f'<circle cx="{_num(peak_x)}" cy="{_num(peak_y)}" r="3" fill="{INK}"/>')
    # Nothing is higher than the maximum, so the label goes above it when
    # the peak is clear of the title, and beside it when it is not.
    if peak_y - top >= 14:
        anchor, label_x, label_y = "middle", peak_x, peak_y - 7
    else:
        anchor = "end" if found.first_max > m / 2 else "start"
        label_x, label_y = peak_x + (-7 if anchor == "end" else 7), peak_y + 4
    out.append(
        f'<text x="{_num(label_x)}" y="{_num(label_y)}" font-size="11" fill="{MUTED}" '
        f'text-anchor="{anchor}">first maximum</text>'
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
    """The chart: one sample walk on top, then four histograms, two by two,
    with their laws: the three arcsine quantities and the longest excursion."""
    edges = bin_edges(steps, bins)
    exact = binned_exact_law(steps, edges)
    limit = binned_arcsine_law(steps, edges)
    max_law = binned_first_max_law(steps, edges)
    longest_law = binned_longest_excursion_law(steps, edges)
    panels = [
        (
            "Time on the positive side",
            histogram((r.positive_time for r in results), edges),
            exact,
            limit,
        ),
        ("Time of the last zero", histogram((r.last_zero for r in results), edges), exact, limit),
        (
            "Time of the first maximum",
            histogram((r.first_max for r in results), edges),
            max_law,
            limit,
        ),
        (
            "Longest excursion",
            histogram((r.longest_excursion for r in results), edges),
            longest_law,
            None,
        ),
    ]
    ymax = max(max(simulated) for _, simulated, _, _ in panels)
    ymax = max(ymax, max(exact), max(limit), max(max_law), max(longest_law))
    ymax = math.ceil(ymax / 0.05 + 0.2) * 0.05

    width, margin, gap = 960, 36, 30
    # The walk panel's labels end 3px above its nominal bottom; the legend
    # row goes under them, then the histograms.
    walk_height = 150 if walk is not None else 0
    hist_top = 70 + (walk_height + 38 if walk is not None else 0)
    hist_height, row_gap = 230, 30
    height = hist_top + 2 * hist_height + row_gap + 8
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
    panel_width = (width - 2 * margin - gap) / 2
    for i, (title, simulated, law, limit_law) in enumerate(panels):
        x0 = margin + (i % 2) * (panel_width + gap)
        y0 = hist_top + (i // 2) * (hist_height + row_gap)
        out.extend(
            _histogram_panel(
                title, simulated, law, limit_law, x0, y0, panel_width, hist_height, ymax
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


def _log_panel(
    title: str,
    series: Sequence[tuple[str, Sequence[tuple[int, float]], float]],
    references: Sequence[tuple[float, str]],
    x0: float,
    y0: float,
    width: float,
    height: float,
    xlim: tuple[int, int],
    ylim: tuple[float, float],
    yticks: Sequence[float],
    tick_format: str,
) -> list[str]:
    """A panel with the walk's length across on a log scale: each series is
    a colour, points (steps, value) and a stroke width, and each reference
    a dashed level with a label at its right end."""
    top, bottom = y0 + 22, y0 + height - 24
    right = x0 + width - 44  # room for the reference labels
    lx0, lx1 = math.log10(xlim[0]), math.log10(xlim[1])

    def x(m: float) -> float:
        return x0 + (math.log10(m) - lx0) / (lx1 - lx0) * (right - x0)

    def y(v: float) -> float:
        return bottom - (v - ylim[0]) / (ylim[1] - ylim[0]) * (bottom - top)

    out = [
        f'<text x="{_num(x0)}" y="{_num(y0 + 6)}" font-size="13" font-weight="600" '
        f'fill="{INK}">{title}</text>'
    ]
    for tick in yticks:
        out.append(
            f'<line x1="{_num(x0)}" y1="{_num(y(tick))}" x2="{_num(right)}" '
            f'y2="{_num(y(tick))}" stroke="{GRID}" stroke-width="1"/>'
        )
        out.append(
            f'<text x="{_num(x0 - 6)}" y="{_num(y(tick) + 4)}" font-size="11" fill="{MUTED}" '
            f'text-anchor="end">{tick:{tick_format}}</text>'
        )
    decade = 10 ** math.ceil(lx0)
    while decade <= xlim[1]:
        out.append(
            f'<text x="{_num(x(decade))}" y="{_num(bottom + 15)}" font-size="11" '
            f'fill="{MUTED}" text-anchor="middle">{decade:,}</text>'
        )
        decade *= 10
    for level, label in references:
        out.append(
            f'<line x1="{_num(x0)}" y1="{_num(y(level))}" x2="{_num(right)}" '
            f'y2="{_num(y(level))}" stroke="{INK}" stroke-width="1" stroke-dasharray="4 3"/>'
        )
        out.append(
            f'<text x="{_num(right + 5)}" y="{_num(y(level) + 4)}" font-size="11" '
            f'fill="{INK}">{label}</text>'
        )
    for color, points, stroke_width in series:
        # On a log scale the long walks crowd together; a point less than
        # half a pixel along from the last one kept adds nothing but bytes.
        kept = [points[0]]
        for point in points[1:-1]:
            if x(point[0]) - x(kept[-1][0]) >= 0.5:
                kept.append(point)
        kept.append(points[-1])
        drawn = " ".join(f"{_num(x(m))},{_num(y(v))}" for m, v in kept)
        out.append(
            f'<polyline points="{drawn}" fill="none" stroke="{color}" '
            f'stroke-width="{stroke_width}" stroke-linejoin="round"/>'
        )
    out.append(
        f'<line x1="{_num(x0)}" y1="{_num(bottom)}" x2="{_num(right)}" y2="{_num(bottom)}" '
        f'stroke="{MUTED}" stroke-width="1"/>'
    )
    return out


def render_longest_svg(steps: int) -> str:
    """The second chart: the exact mean longest excursion and final-stretch
    probability at every even length up to `steps`, closing on their common
    limit, and beside them the two gaps, scaled so that they settle."""
    if steps < 12 or steps % 2:
        raise ValueError("the chart needs an even number of steps, at least 12")
    probabilities = final_stretch_probabilities(steps)
    means = means_from_probabilities(probabilities)
    limit = longest_excursion_limit()
    lengths = range(2, steps + 1, 2)
    left_start, right_start = 10, 4
    mean_fraction = [(m, means[m // 2] / m) for m in lengths if m >= left_start]
    final = [(m, probabilities[m // 2]) for m in lengths if m >= left_start]
    mean_gap = [(m, (means[m // 2] / m - limit) * m) for m in lengths if m >= right_start]
    wobble = {
        r: [(m, (probabilities[m // 2] - limit) * m * m) for m in lengths if m >= right_start]
        for r in (0, 2)
    }
    for r in wobble:
        wobble[r] = [(m, v) for m, v in wobble[r] if m % 4 == r]

    width, margin, gap = 960, 40, 50
    panel_top, panel_height = 94, 320
    height = panel_top + panel_height + 8
    panel_width = (width - 2 * margin - gap) / 2
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Helvetica, Arial, sans-serif" '
        f'font-size="12">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{margin}" y="28" font-size="17" font-weight="600" fill="{INK}">'
        "The longest excursion: the mean and the final stretch share a limit</text>",
        f'<text x="{margin}" y="46" fill="{MUTED}">Exact, for walks of every even length up '
        f"to {steps:,} steps (across, log scale). The limit {limit:.7f} is Brownian "
        "motion's, from an integral.</text>",
    ]
    out.extend(
        _log_panel(
            "Both close on the limit",
            [(BLUE, mean_fraction, 2), (ORANGE, final, 1.5)],
            [(limit, f"{limit:.4f}")],
            margin,
            panel_top,
            panel_width,
            panel_height,
            (left_start, steps),
            (0.62, 0.68),
            [0.62, 0.63, 0.64, 0.65, 0.66, 0.67, 0.68],
            ".2f",
        )
    )
    out.extend(
        _log_panel(
            "The gaps to it, times steps (mean) and steps² (chance)",
            [(BLUE, mean_gap, 2), (ORANGE, wobble[0], 1.5), (ORANGE, wobble[2], 1.5)],
            [(0.5, "½"), (1 / math.pi, "1/π"), (-1 / math.pi, "−1/π")],
            margin + panel_width + gap,
            panel_top,
            panel_width,
            panel_height,
            (right_start, steps),
            (-0.6, 0.8),
            [-0.6, -0.4, -0.2, 0, 0.2, 0.4, 0.6, 0.8],
            ".1f",
        )
    )
    legend_y = panel_top - 22
    items = [
        (BLUE, "mean longest excursion"),
        (ORANGE, "chance the final stretch is the longest"),
    ]
    lx = margin
    for color, label in items:
        out.append(
            f'<line x1="{_num(lx)}" y1="{legend_y}" x2="{_num(lx + 18)}" y2="{legend_y}" '
            f'stroke="{color}" stroke-width="2"/>'
        )
        out.append(
            f'<text x="{_num(lx + 24)}" y="{legend_y + 4}" font-size="11" fill="{MUTED}">'
            f"{label}</text>"
        )
        lx += 24 + len(label) * 6.2 + 24
    out.append(
        f'<line x1="{_num(lx)}" y1="{legend_y}" x2="{_num(lx + 18)}" y2="{legend_y}" '
        f'stroke="{INK}" stroke-width="1" stroke-dasharray="4 3"/>'
    )
    out.append(
        f'<text x="{_num(lx + 24)}" y="{legend_y + 4}" font-size="11" fill="{MUTED}">'
        "the level each settles to</text>"
    )
    out.append("</svg>")
    return "\n".join(out) + "\n"


# --- CLI -----------------------------------------------------------------------------------

REPORTED_LENGTHS = (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000)


def exact_longest_report(steps: int) -> list[str]:
    """The exact mean longest excursion and final-stretch probability at the
    round lengths up to `steps`, and at `steps`, from one pass of the
    recursion, with the gap between the two scaled by the length."""
    probabilities = final_stretch_probabilities(steps)
    means = means_from_probabilities(probabilities)
    lengths = [m for m in REPORTED_LENGTHS if m < steps] + [steps]
    limit = longest_excursion_limit()
    lines = [
        f"walks of {steps} steps, exactly:",
        f"longest excursion, mean fraction: {means[-1] / steps:.6f}",
        f"walks whose final stretch is the longest: {probabilities[-1]:.6f}",
        f"the limit of both, from Brownian motion: {limit:.10f}",
        "",
        "steps   mean fraction   final stretch is longest   (mean - limit) x steps"
        "   (final - limit) x steps^2",
    ]
    for m in lengths:
        mean, final = means[m // 2] / m, probabilities[m // 2]
        lines.append(
            f"{m:5d}   {mean:13.6f}   {final:24.6f}   {(mean - limit) * m:23.4f}"
            f"   {(final - limit) * m * m:26.4f}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Random walks against the arcsine law.")
    parser.add_argument("--steps", type=int, default=1000, help="steps per walk, an even number")
    parser.add_argument("--walks", type=int, default=20000, help="number of walks")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--bins", type=int, default=20)
    parser.add_argument("--out", type=Path, help="write the SVG chart here")
    parser.add_argument(
        "--exact-longest",
        action="store_true",
        help="print the exact mean longest excursion and the chance the final stretch is the "
        "longest, at every length up to --steps, instead of simulating; a fifth of a second "
        "for 1,000 steps, about six for 4,000; with --out, write their chart there",
    )
    args = parser.parse_args(argv)
    steps = args.steps
    if args.exact_longest:
        try:
            lines = exact_longest_report(steps)
            svg = render_longest_svg(steps) if args.out else None
        except ValueError as err:
            print(f"error: {err}", file=sys.stderr)
            return 2
        print("\n".join(lines))
        if svg is not None:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(svg, encoding="utf-8")
            print(f"wrote {args.out}")
        return 0
    try:
        results = simulate(steps, args.walks, args.seed)
        lines = report(steps, results, args.bins)
    except ValueError as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    if args.out:
        # The sample walk is the first one the seed produces.
        walk = random_walk(random.Random(args.seed), steps)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_svg(steps, results, args.bins, walk), encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
