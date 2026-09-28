import itertools
import math
import random
import xml.etree.ElementTree as ET
from fractions import Fraction
from itertools import accumulate
from pathlib import Path

import arcsine
import pytest

HERE = Path(__file__).parent


def every_walk(steps):
    """All 2^steps walks of the given length, as position lists."""
    for signs in itertools.product((1, -1), repeat=steps):
        yield [0, *accumulate(signs)]


@pytest.fixture(scope="module")
def sample():
    steps, walks = 200, 4000
    return steps, arcsine.simulate(steps, walks, seed=1)


# --- walks and measurements -------------------------------------------------


def test_random_walk_starts_at_zero_and_steps_by_one():
    walk = arcsine.random_walk(random.Random(3), 500)
    assert len(walk) == 501
    assert walk[0] == 0
    assert all(abs(b - a) == 1 for a, b in zip(walk, walk[1:], strict=False))


def test_random_walk_is_seeded():
    assert arcsine.random_walk(random.Random(9), 100) == arcsine.random_walk(random.Random(9), 100)
    assert arcsine.random_walk(random.Random(9), 100) != arcsine.random_walk(random.Random(8), 100)
    assert arcsine.random_walk(random.Random(0), 0) == [0]


def test_measure_hand_walk():
    # 0 1 2 1 0 -1 0: the first four intervals are on the positive side (the
    # fourth ends at zero but starts at 1), the last two are not.
    found = arcsine.measure([0, 1, 2, 1, 0, -1, 0])
    assert found == arcsine.Measure(positive_time=4, last_zero=6, first_max=2, longest_excursion=4)


def test_measure_walk_that_never_returns():
    assert arcsine.measure([0, 1, 2, 3, 4]) == (4, 0, 4, 4)
    assert arcsine.measure([0, -1, -2, -1, 0]) == (0, 4, 0, 4)
    assert arcsine.measure([0, -1, 0, 1, 0, -1]) == (2, 4, 3, 2)


def test_first_max_is_the_first_of_equal_maxima():
    # The maximum 1 is reached at steps 1, 3 and 5; the first counts, and a
    # walk that never rises above its start has its maximum at time 0.
    assert arcsine.measure([0, 1, 0, 1, 0, 1]).first_max == 1
    assert arcsine.measure([0, -1, 0, -1, 0]).first_max == 0
    assert arcsine.measure([0]).first_max == 0


def test_measure_counts_the_unfinished_final_stretch():
    # Back at zero at 2, then away for the remaining three steps.
    assert arcsine.measure([0, 1, 0, -1, -2, -1]).longest_excursion == 3


def test_measure_rejects_a_walk_not_starting_at_zero():
    with pytest.raises(ValueError):
        arcsine.measure([1, 2])
    with pytest.raises(ValueError):
        arcsine.measure([])


def test_positive_time_is_even_and_within_range(sample):
    steps, results = sample
    for r in results:
        assert r.positive_time % 2 == 0
        assert 0 <= r.positive_time <= steps
        assert r.last_zero % 2 == 0
        assert 0 <= r.first_max <= steps
        assert r.longest_excursion >= steps - r.last_zero
        assert 2 <= r.longest_excursion <= steps


def test_simulate_is_deterministic_and_validates():
    assert arcsine.simulate(20, 50, seed=4) == arcsine.simulate(20, 50, seed=4)
    assert arcsine.simulate(20, 50, seed=4) != arcsine.simulate(20, 50, seed=5)
    with pytest.raises(ValueError):
        arcsine.simulate(21, 5, seed=1)
    with pytest.raises(ValueError):
        arcsine.simulate(20, 0, seed=1)


# --- the exact laws -----------------------------------------------------------


def test_u_is_the_return_probability():
    assert arcsine.u(0) == 1
    assert arcsine.u(1) == Fraction(1, 2)
    assert arcsine.u(2) == Fraction(3, 8)
    assert arcsine.u(3) == Fraction(5, 16)


@pytest.mark.parametrize("steps", [2, 4, 6, 8, 10])
def test_feller_law_matches_every_walk(steps):
    # Feller: the time on the positive side is 2k in u(k) u(n-k) of the 2^2n
    # walks, and so is the last zero. Count them all.
    positive: dict[int, int] = {}
    last: dict[int, int] = {}
    for walk in every_walk(steps):
        found = arcsine.measure(walk)
        positive[found.positive_time] = positive.get(found.positive_time, 0) + 1
        last[found.last_zero] = last.get(found.last_zero, 0) + 1
    law = arcsine.exact_law(steps // 2)
    assert positive == {2 * k: p * 2**steps for k, p in enumerate(law)}
    assert last == {2 * k: p * 2**steps for k, p in enumerate(law)}


@pytest.mark.parametrize("steps", [2, 4, 6, 8, 10])
def test_first_max_law_matches_every_walk(steps):
    # Feller: the first maximum is at time 0 in u(n) of the walks and at
    # time k >= 1 in u(k // 2) u(n - k // 2) / 2 of them. Count them all,
    # and count the last maximum too: its law is the first's reversed.
    first: dict[int, int] = {}
    last: dict[int, int] = {}
    for walk in every_walk(steps):
        top = max(walk)
        first[walk.index(top)] = first.get(walk.index(top), 0) + 1
        last_max = steps - walk[::-1].index(top)
        last[last_max] = last.get(last_max, 0) + 1
    law = arcsine.first_max_law(steps // 2)
    assert len(law) == steps + 1
    assert first == {k: p * 2**steps for k, p in enumerate(law)}
    assert last == {steps - k: p * 2**steps for k, p in enumerate(law)}
    assert first[0] == sum(1 for walk in every_walk(steps) if max(walk) == 0)


def test_first_max_law_is_the_arcsine_law_with_the_ends_moved():
    # Times 2j and 2j + 1 together carry the arcsine atom u(j) u(n - j),
    # except that the atom at 0 is whole and the one at 2n is halved: the
    # tie between equal maxima goes to the earlier time.
    n = 500
    law = arcsine.first_max_law(n)
    atoms = arcsine.exact_law(n)
    assert sum(law) == 1
    assert law[0] == atoms[0]
    assert law[1] == atoms[0] / 2
    assert law[2 * n] == atoms[n] / 2
    for j in range(1, n):
        assert law[2 * j] == law[2 * j + 1] == atoms[j] / 2
    # So the maximum leans early: the mean time is (n + 1/2)(1 - u(n)), not n.
    assert sum(k * p for k, p in enumerate(law)) == Fraction(2 * n + 1, 2) * (1 - arcsine.u(n))
    assert sum(law[: 2 * n // 10 + 1]) > sum(law[2 * n * 9 // 10 :])


@pytest.mark.parametrize("steps", [2, 4, 6, 8, 10])
def test_longest_excursion_law_matches_every_walk(steps):
    longest = [arcsine.measure(walk).longest_excursion for walk in every_walk(steps)]
    for max_len in range(-1, steps + 2):
        expected = Fraction(sum(1 for x in longest if x <= max_len), 2**steps)
        assert arcsine.longest_excursion_cdf(steps, max_len, exact=True) == expected, max_len
    assert arcsine.longest_excursion_cdf(steps, steps) == pytest.approx(1.0)


@pytest.mark.parametrize("steps", [2, 4, 6, 8, 10])
def test_final_stretch_and_mean_longest_match_every_walk(steps):
    found = [arcsine.measure(walk) for walk in every_walk(steps)]
    final = Fraction(sum(1 for r in found if steps - r.last_zero == r.longest_excursion), 2**steps)
    mean = Fraction(sum(r.longest_excursion for r in found), 2**steps)
    assert arcsine.final_stretch_is_longest(steps, exact=True) == final
    assert arcsine.mean_longest_excursion(steps, exact=True) == mean
    assert arcsine.final_stretch_is_longest(steps) == pytest.approx(float(final))
    assert arcsine.mean_longest_excursion(steps) == pytest.approx(float(mean))


def test_two_more_steps_lengthen_the_longest_excursion_iff_the_final_stretch_is_longest():
    # The identity behind mean_longest_excursions, on every walk of up to
    # ten steps and every way of adding two steps to it.
    for steps in (0, 2, 4, 6, 8, 10):
        for walk in every_walk(steps):
            before = arcsine.measure(walk)
            grows = steps - before.last_zero == before.longest_excursion
            for a, b in itertools.product((1, -1), repeat=2):
                longer = [*walk, walk[-1] + a, walk[-1] + a + b]
                after = arcsine.measure(longer).longest_excursion
                assert after == before.longest_excursion + 2 * grows, (walk, a, b)


def test_the_lists_hold_every_shorter_length():
    # One pass gives every even length up to the one asked for, and the
    # means are twice the running sums of the probabilities.
    probabilities = arcsine.final_stretch_probabilities(20, exact=True)
    means = arcsine.mean_longest_excursions(20, exact=True)
    assert len(probabilities) == len(means) == 11
    assert probabilities[0] == 1 and means[0] == 0 and means[1] == 2
    for k in range(1, 11):
        assert probabilities[k] == arcsine.final_stretch_is_longest(2 * k, exact=True)
        assert means[k] == arcsine.mean_longest_excursion(2 * k, exact=True)
        assert means[k] == 2 * sum(probabilities[:k])
    assert arcsine.means_from_probabilities(probabilities) == means
    # 4, 6, 10 and 14 steps give exactly 5/8; 8, 12 and 16 do not.
    assert [probabilities[k] == Fraction(5, 8) for k in (2, 3, 5, 7, 4, 6, 8)] == [True] * 4 + [
        False
    ] * 3
    for bad in (0, -2, 7):
        with pytest.raises(ValueError):
            arcsine.final_stretch_probabilities(bad)
        with pytest.raises(ValueError):
            arcsine.mean_longest_excursions(bad)


def test_short_excursion_rows_agree_with_the_plain_recursion():
    # The rows use closed forms up to twice the limit and a dot product
    # after; the plain recursion over first returns must give the same.
    for exact in (True, False):
        us = arcsine.return_probabilities(30, exact)
        first_return = [None] + [us[j - 1] - us[j] for j in range(1, 31)]
        for limit in range(31):
            row = arcsine._short_excursion_returns(us, limit, 30)
            assert len(row) == 31
            plain = [us[0]]
            for s in range(1, 31):
                plain.append(
                    sum(first_return[j] * plain[s - j] for j in range(1, min(limit, s) + 1))
                )
            if exact:
                assert row == plain, limit
            else:
                assert row == pytest.approx(plain, abs=1e-15), limit
    assert arcsine._short_excursion_returns(arcsine.return_probabilities(5, True), 0, 5) == [
        1,
        0,
        0,
        0,
        0,
        0,
    ]


def test_final_stretch_probability_settles_while_the_mean_keeps_falling():
    # What the write-up says: the mean longest excursion is still shrinking
    # with the walk length, while the chance that the final stretch is the
    # longest is 0.6264 at 50 steps and 0.6265 from 100 steps up, 1,000
    # included, and the mean exceeds it by about half a step: the gap times
    # the number of steps is 0.4984 at 200 steps and 0.4997 at 1,000. This
    # runs the recursion at 1,000 steps, in a fraction of a second.
    probabilities = arcsine.final_stretch_probabilities(1000)
    means = arcsine.mean_longest_excursions(1000)
    fractions = {m: means[m // 2] / m for m in (20, 50, 100, 200, 1000)}
    assert fractions[20] > fractions[50] > fractions[100] > fractions[200] > fractions[1000]
    assert round(fractions[1000], 4) == 0.6270
    assert round(probabilities[25], 4) == 0.6264
    assert round(probabilities[50], 4) == 0.6265
    assert round(probabilities[100], 4) == 0.6265
    assert round(probabilities[500], 6) == 0.626508
    assert round((fractions[200] - probabilities[100]) * 200, 4) == 0.4984
    assert round((fractions[1000] - probabilities[500]) * 1000, 4) == 0.4997


def test_exact_law_is_a_symmetric_distribution():
    law = arcsine.exact_law(500)
    assert sum(law) == 1
    assert law == law[::-1]
    assert law[0] > law[250]


def test_exact_law_is_close_to_the_limit_at_a_thousand_steps():
    steps = 1000
    edges = arcsine.bin_edges(steps, 20)
    feller = arcsine.binned_exact_law(steps, edges)
    limit = arcsine.binned_arcsine_law(steps, edges)
    assert sum(feller) == pytest.approx(1.0)
    assert sum(limit) == pytest.approx(1.0)
    # The bins are half-open except the top one, which is closed at 1, so
    # it holds one more atom of the discrete law than the bottom one: the
    # value 950, the mirror of the value 50 that sits in the second bin,
    # with mass u(25) u(475), about 0.003. That asymmetry is the 0.002 gap
    # here, not a difference between the laws.
    assert max(abs(a - b) for a, b in zip(feller, limit, strict=True)) < 0.003
    assert max(abs(a - b) for a, b in zip(feller[:-1], limit[:-1], strict=True)) < 0.001


def test_arcsine_cdf_endpoints_and_headline():
    assert arcsine.arcsine_cdf(0) == 0
    assert arcsine.arcsine_cdf(1) == pytest.approx(1.0)
    assert arcsine.arcsine_cdf(0.5) == pytest.approx(0.5)
    # Nearly 41% of walks spend at least nine tenths of the time on one side.
    assert 2 * arcsine.arcsine_cdf(0.1) == pytest.approx(0.4097, abs=1e-4)


# --- the simulation against the laws -------------------------------------------


def test_simulation_follows_feller_law(sample):
    steps, results = sample
    law = arcsine.exact_law(steps // 2)
    positive = [r.positive_time for r in results]
    last = [r.last_zero for r in results]
    first_max = [r.first_max for r in results]
    assert arcsine.ks_distance(positive, law, 2) < 0.03
    assert arcsine.ks_distance(last, law, 2) < 0.03
    assert arcsine.ks_distance(first_max, arcsine.first_max_law(steps // 2), 1) < 0.03


def test_ks_distance_is_zero_for_the_law_itself_and_reads_the_spacing():
    # Values drawn to match the law exactly are at distance 0; the same
    # values against a law placed at the wrong spacing are not.
    law = [Fraction(1, 4), Fraction(1, 2), Fraction(1, 4)]
    values = [0, 2, 2, 4]
    assert arcsine.ks_distance(values, law, 2) == 0
    assert arcsine.ks_distance(values, law, 1) == pytest.approx(0.5)
    assert arcsine.ks_distance([0, 1, 1, 2], law, 1) == 0


def test_simulation_follows_the_longest_excursion_law(sample):
    steps, results = sample
    edges = arcsine.bin_edges(steps, 10)
    simulated = arcsine.histogram((r.longest_excursion for r in results), edges)
    law = arcsine.binned_longest_excursion_law(steps, edges)
    assert sum(law) == pytest.approx(1.0)
    assert max(abs(a - b) for a, b in zip(simulated, law, strict=True)) < 0.02


def test_binning():
    edges = arcsine.bin_edges(1000, 20)
    assert edges[:3] == [0, 50, 100]
    assert arcsine.bin_of(0, edges) == 0
    assert arcsine.bin_of(49, edges) == 0
    assert arcsine.bin_of(50, edges) == 1
    assert arcsine.bin_of(1000, edges) == 19
    assert arcsine.histogram([0, 49, 50, 1000], edges)[0] == 0.5
    with pytest.raises(ValueError):
        arcsine.bin_edges(1000, 0)


def test_bins_must_divide_the_steps():
    # The chart draws every bin the same width and says so, so unequal bins
    # are refused rather than drawn wrong.
    assert arcsine.bin_edges(30, 5) == [0, 6, 12, 18, 24]
    for steps, bins in ((100, 30), (2, 5), (10, 3)):
        with pytest.raises(ValueError, match="divide"):
            arcsine.bin_edges(steps, bins)


def test_report_has_headline_and_bins(sample):
    steps, results = sample
    lines = arcsine.report(steps, results, bins=10)
    assert lines[0] == f"{len(results)} walks of {steps} steps"
    assert any(line.startswith("walks at least 90% on one side") for line in lines)
    assert len([line for line in lines if line.startswith("0.")]) == 10


# --- the chart -------------------------------------------------------------------


def test_positive_pieces_include_the_zeros_at_each_end():
    assert arcsine.positive_pieces([0, 1, 2, 1, 0, -1, 0]) == [(0, 4)]
    assert arcsine.positive_pieces([0, -1, 0, 1, 0, 1, 2]) == [(2, 4), (4, 6)]
    assert arcsine.positive_pieces([0, -1, -2]) == []


def test_svg_is_well_formed_and_holds_the_panels(sample):
    steps, results = sample
    walk = arcsine.random_walk(random.Random(1), steps)
    svg = arcsine.render_svg(steps, results, bins=20, walk=walk)
    root = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    rects = list(root.iter(f"{ns}rect"))
    assert len(rects) == 1 + 4 * 20 + 1  # background, bars, legend swatch
    # The exact laws' dots, the legend's dot, and the walk's first maximum.
    assert len(list(root.iter(f"{ns}circle"))) == 4 * 20 + 1 + 1
    text = " ".join(t.text or "" for t in root.iter(f"{ns}text"))
    for title in (
        "Time on the positive side",
        "Time of the last zero",
        "Time of the first maximum",
        "Longest excursion",
    ):
        assert title in text
    assert "last zero" in text and "longest excursion" in text and "first maximum" in text
    assert "<" not in text  # nothing unescaped
    # Four panels, two by two: two distinct x positions and two distinct y
    # positions among the bars, and the chart is taller than it is wide is not
    # required, but the panels must not overlap the walk or each other.
    bars = rects[1:-1]
    xs = sorted({float(r.get("x")) for r in bars})
    tops = sorted({float(r.get("y")) + float(r.get("height")) for r in bars})
    assert len(xs) == 40 and len(tops) == 2
    assert xs[20] > xs[19] + 20  # a gap between the columns


def test_svg_without_a_walk_is_shorter(sample):
    steps, results = sample
    with_walk = arcsine.render_svg(
        steps, results, walk=arcsine.random_walk(random.Random(1), steps)
    )
    without = arcsine.render_svg(steps, results)
    assert len(without) < len(with_walk)
    ET.fromstring(without)


def test_cli_writes_chart(tmp_path, capsys):
    out = tmp_path / "chart.svg"
    assert arcsine.main(["--steps", "100", "--walks", "300", "--seed", "2", "--out", str(out)]) == 0
    assert out.exists()
    ET.fromstring(out.read_text())
    printed = capsys.readouterr().out
    assert printed.startswith("300 walks of 100 steps")
    assert f"wrote {out}" in printed


def test_cli_rejects_odd_steps(capsys):
    assert arcsine.main(["--steps", "99", "--walks", "10"]) == 2
    assert "even" in capsys.readouterr().err
    assert arcsine.main(["--steps", "99", "--exact-longest"]) == 2
    assert "even" in capsys.readouterr().err


def test_cli_rejects_bins_that_do_not_divide_the_steps(capsys):
    assert arcsine.main(["--steps", "100", "--bins", "30", "--walks", "10"]) == 2
    assert "divide" in capsys.readouterr().err


def test_cli_exact_longest_shares_the_default_and_writes_its_chart(tmp_path, capsys):
    # The exact computations run at the simulation's 1,000 steps by default,
    # in a fraction of a second, and --out writes their chart.
    assert arcsine.main(["--exact-longest"]) == 0
    printed = capsys.readouterr().out
    assert printed.startswith("walks of 1000 steps")
    assert "\n 1000   " in printed and "\n  500   " in printed and "\n   10   " in printed
    assert "2000" not in printed  # lengths beyond the one asked for are not listed
    out = tmp_path / "longest.svg"
    assert arcsine.main(["--steps", "40", "--exact-longest", "--out", str(out)]) == 0
    assert f"wrote {out}" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == arcsine.render_longest_svg(40)
    # Below 12 steps the left panel, which starts at 10, has nothing to draw.
    short = tmp_path / "short.svg"
    for steps in ("2", "10"):
        assert arcsine.main(["--steps", steps, "--exact-longest", "--out", str(short)]) == 2
        assert "at least 12" in capsys.readouterr().err
    assert not short.exists()


def test_exact_longest_report_builds_the_table_once(monkeypatch):
    # The means come from the probabilities already computed, not from a
    # second run of the cubic recursion.
    calls = []
    table = arcsine.final_stretch_probabilities

    def counted(steps, exact=False):
        calls.append(steps)
        return table(steps, exact)

    monkeypatch.setattr(arcsine, "final_stretch_probabilities", counted)
    lines = arcsine.exact_longest_report(40)
    assert calls == [40]
    assert lines[-1].split()[:2] == ["40", f"{arcsine.mean_longest_excursion(40) / 40:.6f}"]


def test_cli_exact_longest(capsys):
    assert arcsine.main(["--steps", "8", "--exact-longest"]) == 0
    out = capsys.readouterr().out
    assert "mean fraction: 0.687500" in out  # 11/16, from the enumeration test
    assert "final stretch is the longest: 0.632812" in out  # 81/128
    rows = [line for line in out.splitlines() if line.strip().startswith("8 ")]
    assert len(rows) == 1  # 8 steps is below every round length, so it is the only row
    limit = arcsine.longest_excursion_limit()
    assert "from Brownian motion: 0.6265075988" in out
    assert rows[0].split() == [
        "8",
        "0.687500",
        "0.632812",
        f"{(Fraction(11, 16) - limit) * 8:.4f}",
        f"{(Fraction(81, 128) - limit) * 64:.4f}",
    ]


def test_the_integral_is_converged():
    # Doubling the number of Simpson intervals moves the value by about
    # 2e-12, far below the ten places the README quotes.
    limit = arcsine.longest_excursion_limit()
    assert abs(limit - arcsine.longest_excursion_limit(40000)) < 1e-11
    assert f"{limit:.10f}" == "0.6265075988"
    with pytest.raises(ValueError):
        arcsine.longest_excursion_limit(201)


def test_the_recursion_closes_on_the_integral():
    # Two independent computations of one constant: the random walk's exact
    # renewal sum and Brownian motion's integral. The probability's gap to
    # the integral is about (-1)^(steps/2) / (pi steps^2), and the mean's is
    # half a step, to within a thousandth of each by 2,000 steps.
    steps = 2000
    probabilities = arcsine.final_stretch_probabilities(steps)
    means = arcsine.means_from_probabilities(probabilities)
    limit = arcsine.longest_excursion_limit()
    for m in (steps - 2, steps):
        sign = 1 if m % 4 == 0 else -1
        assert abs((probabilities[m // 2] - limit) * m * m - sign / math.pi) < 1e-3
        assert abs((means[m // 2] / m - limit) * m - 0.5) < 1e-3
    assert abs(probabilities[-1] - limit) < 1e-7


def test_longest_chart_is_well_formed_and_holds_both_panels():
    svg = arcsine.render_longest_svg(100)
    root = ET.fromstring(svg)
    ns = "{http://www.w3.org/2000/svg}"
    texts = ["".join(t.itertext()) for t in root.iter(f"{ns}text")]
    assert "Both close on the limit" in texts
    assert any(t.startswith("The gaps to it") for t in texts)
    assert {"½", "1/π", "−1/π", "0.6265"} <= set(texts)
    # Two series on the left; on the right the mean and the probability's
    # two branches, lengths 0 and 2 mod 4.
    lines = list(root.iter(f"{ns}polyline"))
    assert len(lines) == 5
    # The left panel starts at 10 steps: 46 even lengths up to 100.
    assert [len(p.get("points").split()) for p in lines[:2]] == [46, 46]
    # The right starts at 4: 49 lengths, 25 of them 0 mod 4 (4 to 100 by 4) and 24 not.
    assert [len(p.get("points").split()) for p in lines[2:]] == [49, 25, 24]


def test_committed_longest_chart_matches_the_code():
    # Regenerated with --exact-longest --steps 2000, as the README says.
    expected = arcsine.render_longest_svg(2000)
    assert (HERE / "out" / "longest.svg").read_text(encoding="utf-8") == expected


def test_committed_chart_matches_the_code():
    # Regenerated with the defaults, as the README says.
    steps, walks, seed = 1000, 20000, 1
    results = arcsine.simulate(steps, walks, seed)
    walk = arcsine.random_walk(random.Random(seed), steps)
    expected = arcsine.render_svg(steps, results, 20, walk)
    assert (HERE / "out" / "arcsine.svg").read_text(encoding="utf-8") == expected
