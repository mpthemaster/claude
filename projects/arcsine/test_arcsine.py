import itertools
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
    assert found == arcsine.Measure(positive_time=4, last_zero=6, longest_excursion=4)


def test_measure_walk_that_never_returns():
    assert arcsine.measure([0, 1, 2, 3, 4]) == (4, 0, 4)
    assert arcsine.measure([0, -1, -2, -1, 0]) == (0, 4, 4)
    assert arcsine.measure([0, -1, 0, 1, 0, -1]) == (2, 4, 2)


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


def test_final_stretch_probability_settles_while_the_mean_keeps_falling():
    # What the write-up says: the mean longest excursion is still shrinking
    # with the walk length, while the chance that the final stretch is the
    # longest is 0.6264 at 50 steps and 0.6265 from 100 steps up.
    means = [arcsine.mean_longest_excursion(m) / m for m in (20, 50, 100, 200)]
    assert means[0] > means[1] > means[2] > means[3] > 0.62
    assert round(arcsine.final_stretch_is_longest(50), 4) == 0.6264
    assert round(arcsine.final_stretch_is_longest(100), 4) == 0.6265
    assert round(arcsine.final_stretch_is_longest(200), 4) == 0.6265


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
    assert arcsine.ks_distance(positive, law, steps) < 0.03
    assert arcsine.ks_distance(last, law, steps) < 0.03


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
    assert len(rects) == 1 + 3 * 20 + 1  # background, bars, legend swatch
    assert len(list(root.iter(f"{ns}circle"))) == 3 * 20 + 1  # exact laws, legend dot
    text = " ".join(t.text or "" for t in root.iter(f"{ns}text"))
    for title in ("Time on the positive side", "Time of the last zero", "Longest excursion"):
        assert title in text
    assert "last zero" in text and "longest excursion" in text
    assert "<" not in text  # nothing unescaped


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


def test_cli_exact_longest(capsys):
    assert arcsine.main(["--steps", "8", "--exact-longest"]) == 0
    out = capsys.readouterr().out
    assert "mean fraction: 0.687500" in out  # 11/16, from the enumeration test
    assert "final stretch is the longest: 0.632812" in out  # 81/128


def test_committed_chart_matches_the_code():
    # Regenerated with the defaults, as the README says.
    steps, walks, seed = 1000, 20000, 1
    results = arcsine.simulate(steps, walks, seed)
    walk = arcsine.random_walk(random.Random(seed), steps)
    expected = arcsine.render_svg(steps, results, 20, walk)
    assert (HERE / "out" / "arcsine.svg").read_text(encoding="utf-8") == expected
