import math
import random
import xml.etree.ElementTree as ET
from decimal import Decimal
from fractions import Fraction

import lookandsay as las
import pytest

DECAY = las.discover()
ELEMENTS = las.elements(DECAY)


def test_step_reads_aloud():
    assert las.step("1") == "11"
    assert las.step("1211") == "111221"
    assert las.step("3") == "13"
    assert las.terms(6) == ["1", "11", "21", "1211", "111221", "312211"]


def brute_first_digits(r, steps=20):
    seen = set()
    for _ in range(steps):
        seen.add(r[0])
        r = las.step(r)
    return seen


def test_first_digits_matches_brute_force_on_every_element_suffix():
    for e in ELEMENTS:
        for i in range(1, len(e)):
            assert las.first_digits(e[i:]) == brute_first_digits(e[i:]), (e, i)


@pytest.mark.parametrize("cap", [8, 32])
def test_first_digits_does_not_depend_on_the_cap(cap):
    for e in ELEMENTS:
        for i in range(1, len(e)):
            assert las.first_digits(e[i:], cap) == las.first_digits(e[i:])


def test_splits_hold_for_many_steps():
    s = las.terms(16)[-1]
    pieces = las.decompose(s)
    assert len(pieces) > 5
    evolved_whole, evolved_pieces = s, pieces
    for _ in range(10):
        evolved_whole = las.step(evolved_whole)
        evolved_pieces = [las.step(p) for p in evolved_pieces]
        assert "".join(evolved_pieces) == evolved_whole


def test_a_rejected_split_really_fails():
    # the two 2s would merge at once
    assert not las.splits("2213", 1)
    s = "1113213211"
    for i in range(1, len(s)):
        if not las.splits(s, i):
            left, right = s[:i], s[i:]
            failed = False
            for _ in range(12):
                if las.step(left + right) != las.step(left) + las.step(right):
                    failed = True
                    break
                left, right = las.step(left), las.step(right)
            assert failed, i


def test_the_elements_are_conways_92():
    assert len(ELEMENTS) == 92
    assert max(len(e) for e in ELEMENTS) == 42
    assert DECAY["22"] == ["22"]  # hydrogen is its own descendant
    assert "3" in ELEMENTS  # uranium
    transients = sorted(set(DECAY) - set(ELEMENTS), key=len)
    assert set(transients) == set(las.terms(7))
    assert las.decompose(las.terms(8)[-1]) == ["11132", "13211"]


def test_each_element_becomes_exactly_its_children():
    for e in ELEMENTS:
        assert "".join(DECAY[e]) == las.step(e)
        assert all(child in ELEMENTS for child in DECAY[e])


def test_counted_lengths_match_real_strings():
    real = [len(t) for t in las.terms(40)]
    assert las.lengths(40) == real


def test_known_length():
    # OEIS A005341: the 50th term has 894810 digits
    assert las.lengths(50)[-1] == 894810


def faddeev_leverrier(m):
    n = len(m)
    a = [[Fraction(v) for v in row] for row in m]
    coeffs = [Fraction(0)] * (n + 1)
    coeffs[n] = Fraction(1)
    mk = [[Fraction(0)] * n for _ in range(n)]
    for k in range(1, n + 1):
        prod = [[sum(a[i][t] * mk[t][j] for t in range(n)) for j in range(n)] for i in range(n)]
        for i in range(n):
            prod[i][i] += coeffs[n - k + 1]
        mk = prod
        am = [[sum(a[i][t] * mk[t][j] for t in range(n)) for j in range(n)] for i in range(n)]
        coeffs[n - k] = -sum(am[i][i] for i in range(n)) / k
    return [int(c) for c in coeffs]


def test_charpoly_small_cases():
    assert las.charpoly([[2, 1], [1, 1]]) == [1, -3, 1]
    rng = random.Random(4)
    for size in (1, 3, 6, 9):
        m = [[rng.randint(-3, 3) for _ in range(size)] for _ in range(size)]
        assert las.charpoly(m) == faddeev_leverrier(m)
    zeros = [[0, 1, 0], [0, 0, 1], [0, 0, 0]]  # needs the no-pivot branch
    assert las.charpoly(zeros) == faddeev_leverrier(zeros)


@pytest.fixture(scope="module")
def conway():
    poly = las.charpoly(las.decay_matrix(ELEMENTS, DECAY))
    powers, rest = las.factor_trivial(poly)
    return poly, powers, rest


def test_conways_factorization(conway):
    poly, powers, rest = conway
    assert len(poly) == 93
    assert powers == {0: 18, 1: 2, -1: 1}
    assert len(rest) - 1 == 71


def test_conways_constant(conway):
    _, _, rest = conway
    lam = las.newton_root(rest, 1.3, digits=40)
    assert str(lam).startswith("1.303577269034296391257099112152551890730")
    ls = las.lengths(501)
    ratio = Decimal(ls[500]) / Decimal(ls[499])
    assert abs(ratio - lam) < Decimal(10) ** -24  # the error shrinks by 0.89 per term


def test_roots_and_the_second_eigenvalue(conway):
    _, _, rest = conway
    roots = sorted(las.all_roots(rest), key=abs, reverse=True)
    for z in roots:
        value = sum(c * z**d for d, c in enumerate(rest))
        scale = sum(abs(c) * abs(z) ** d for d, c in enumerate(rest))
        assert abs(value) < 1e-9 * scale
    assert abs(roots[0] - 1.3035772690342964) < 1e-12
    assert abs(abs(roots[1]) - abs(roots[2])) < 1e-12  # a conjugate pair
    assert 1.16 < abs(roots[1]) < 1.162


def test_settled():
    target = Decimal("1.2345")
    ratios = [Fraction(1), Fraction(12346, 10000), Fraction(12, 10), Fraction(1234, 1000)]
    assert las.settled(ratios, target, 4) == 3
    assert las.settled(ratios, target, 5) is None
    assert las.settled(ratios[3:], target, 2) == 0


def test_six_digits_from_term_80(conway):
    _, _, rest = conway
    lam = las.newton_root(rest, 1.3, digits=30)
    ls = las.lengths(401)
    ratios = [Fraction(ls[n + 1], ls[n]) for n in range(400)]
    assert las.settled(ratios, lam, 6) + 1 == 80
    six = [n for n in range(1, 80) if math.floor(ratios[n - 1] * 10**5) == 130357]
    assert six == [66, 70, 71, 72, 74, 77, 78]
    assert str(ratios[79].numerator / ratios[79].denominator).startswith("1.30357")
    assert not str(ratios[78].numerator / ratios[78].denominator).startswith("1.30357")


def test_main_writes_a_chart(tmp_path, capsys):
    out = tmp_path / "c.svg"
    assert las.main(["--terms", "300", "--out", str(out)]) == 0
    ET.parse(out)
    text = capsys.readouterr().out
    assert "92" in text and "degree-71" in text and "6 digits: from n = 80" in text


@pytest.mark.parametrize("n", [3, 66, 67])
def test_short_runs_still_judge_settling_over_the_full_horizon(n, tmp_path, capsys):
    out = tmp_path / "c.svg"
    assert las.main(["--terms", str(n), "--out", str(out)]) == 0
    ET.parse(out)
    text = capsys.readouterr().out
    assert "6 digits: from n = 80" in text
    assert f"length({n + 1}) / length({n}) does not agree" in text


def test_terms_must_be_positive():
    with pytest.raises(SystemExit):
        las.main(["--terms", "0"])


# --- names and abundances -------------------------------------------------


@pytest.fixture(scope="module")
def lam(conway):
    _, _, rest = conway
    return las.newton_root(rest, 1.3, digits=50)


@pytest.fixture(scope="module")
def shares(lam):
    return dict(zip(ELEMENTS, las.abundances(las.decay_matrix(ELEMENTS, DECAY), lam), strict=True))


NAMES = las.conway_names(DECAY, ELEMENTS)


def test_four_chains_from_uranium_to_hydrogen():
    found = las.chains(DECAY, ELEMENTS)
    assert len(found) == 4
    for chain in found:
        assert sorted(chain) == sorted(ELEMENTS)
        assert chain[0] == "3" and chain[-1] == "22"
        assert all(lower in DECAY[upper] for upper, lower in zip(chain, chain[1:], strict=False))


def test_conways_names():
    assert sorted(NAMES.values()) == sorted(las.SYMBOLS)
    assert len(las.SYMBOLS) == 92
    # entries of Conway's table beyond the one (tin) used to pick the chain
    known = {
        "H": "22",
        "He": "13112221133211322112211213322112",
        "Li": "312211322212221121123222112",
        "Ca": "12",
        "Fe": "13122112",
        "Zn": "312",
        "Hf": "11132",
        "Th": "1113",
        "Pa": "13",
        "U": "3",
    }
    for symbol, string in known.items():
        assert NAMES[string] == symbol


def test_counts_at_agrees_with_lengths():
    ls = las.lengths(30)
    for n in (1, 2, 8, 30):
        assert sum(c * len(p) for p, c in las.counts_at(n).items()) == ls[n - 1]
    assert las.counts_at(8) == {"11132": 1, "13211": 1}


def test_abundances_are_the_perron_vector(lam, shares):
    assert abs(sum(shares.values()) - 1) < Decimal(10) ** -45
    assert all(a > 0 for a in shares.values())
    m = las.decay_matrix(ELEMENTS, DECAY)
    a = [shares[e] for e in ELEMENTS]
    for j in range(len(ELEMENTS)):
        flowing_in = sum(a[i] * m[i][j] for i in range(len(ELEMENTS)))
        assert abs(flowing_in - lam * a[j]) < Decimal(10) ** -45


def test_abundances_match_conways_table(shares):
    # Conway's published abundances, in atoms per million
    assert f"{shares['22'] * 10**6:.3f}" == "91790.383"
    assert f"{shares['11131221131211322113322112'] * 10**6:.4f}" == "27.2462"


def test_abundances_match_counts_at_term_1000(shares):
    counts = las.counts_at(1000)
    total = sum(counts.values())
    assert set(counts) == set(ELEMENTS)
    for e, a in shares.items():
        assert las.agreeing_digits(Decimal(counts[e]) / Decimal(total), a) >= 45


def test_an_element_with_one_source_is_one_lambda_as_common(lam, shares):
    single = 0
    for e in ELEMENTS:
        sources = [(p, DECAY[p].count(e)) for p in ELEMENTS if e in DECAY[p]]
        if len(sources) == 1 and sources[0][1] == 1:
            single += 1
            assert abs(lam * shares[e] - shares[sources[0][0]]) < Decimal(10) ** -45
    assert single == 75


def test_agreeing_digits():
    assert las.agreeing_digits(Decimal("1.2345"), Decimal("1.2346")) == 4
    assert las.agreeing_digits(Decimal(2), Decimal(1)) == 0


def test_main_writes_the_abundance_chart(tmp_path, capsys):
    out = tmp_path / "a.svg"
    assert las.main(["--abundance-out", str(out)]) == 0
    root = ET.parse(out).getroot()
    dots = root.findall("{http://www.w3.org/2000/svg}circle")
    assert len(dots) == 92
    assert dots[0].find("{http://www.w3.org/2000/svg}title").text.startswith("1 H = 22: 91,790")
    text = capsys.readouterr().out
    assert "chains from U down to H, each element decaying into the next: 4" in text
    assert "term 1000 agrees to" in text
