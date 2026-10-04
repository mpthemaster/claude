import math
import random
import subprocess
import xml.etree.ElementTree as ET

import benford
import pytest


def test_benford_probabilities_sum_to_one():
    assert sum(benford.BENFORD) == pytest.approx(1)
    assert benford.BENFORD[0] == pytest.approx(math.log10(2))


@pytest.mark.parametrize(
    "x, digit",
    [(1, 1), (9, 9), (10, 1), (472, 4), (0.0031, 3), (9.99e-12, 9), (2.5e300, 2), (7.0, 7)],
)
def test_first_digit(x, digit):
    assert benford.first_digit(x) == digit


@pytest.mark.parametrize("x", [0, -5, math.inf, math.nan])
def test_first_digit_rejects_non_positive(x):
    with pytest.raises(ValueError):
        benford.first_digit(x)


def test_digit_counts_skips_zero():
    assert benford.digit_counts([0, 1, 12, 300, 0, 9]) == [2, 0, 1, 0, 0, 0, 0, 0, 1]


def test_exact_benford_counts_have_zero_deviation():
    counts = [round(b * 10**6) for b in benford.BENFORD]
    assert benford.mad(counts) < 1e-6
    assert benford.chi_square(counts) < 1e-3


def test_uniform_digits_are_far_from_benford():
    counts = [100] * 9
    # |1/9 - b| averaged over the digits.
    expected = sum(abs(1 / 9 - b) for b in benford.BENFORD) / 9
    assert benford.mad(counts) == pytest.approx(expected)
    assert benford.verdict(benford.mad(counts)) == "nonconformity"


@pytest.mark.parametrize(
    "deviation, name",
    [
        (0.0, "close conformity"),
        (0.006, "close conformity"),
        (0.0061, "acceptable conformity"),
        (0.013, "marginal conformity"),
        (0.02, "nonconformity"),
    ],
)
def test_verdict(deviation, name):
    assert benford.verdict(deviation) == name


def test_log_uniform_sample_conforms_and_stays_flat_under_rescaling():
    rng = random.Random(4)
    values = [10 ** rng.uniform(0, 6) for _ in range(20000)]
    counts = benford.digit_counts(values)
    assert benford.verdict(benford.mad(counts)) == "close conformity"
    sweep = benford.scale_sweep(values, steps=20)
    assert len(sweep) == 21
    assert sweep[0][0] == 1 and sweep[-1][0] == pytest.approx(10)
    assert max(m for _, m in sweep) < 0.006


def test_narrow_sample_swings_under_rescaling():
    # Everything between 70 and 80: all 7s, until the factor moves it.
    values = list(range(70, 80))
    sweep = dict(benford.scale_sweep(values, steps=10))
    assert benford.digit_counts(values)[6] == 10
    assert max(sweep.values()) - min(sweep.values()) > 0.02


def test_expected_mad_matches_simulation():
    rng = random.Random(7)
    n, trials = 200, 400
    total = sum(
        benford.mad(benford.digit_counts(10 ** rng.random() for _ in range(n)))
        for _ in range(trials)
    )
    assert total / trials == pytest.approx(benford.expected_mad(n), rel=0.1)
    assert benford.expected_mad(4 * n) == pytest.approx(benford.expected_mad(n) / 2)


def test_log_spread():
    assert benford.log_spread([10, 1000]) == pytest.approx(1)
    assert benford.log_spread([5, 5, 5]) == 0


def test_file_sizes(tmp_path):
    (tmp_path / "a").write_bytes(b"x" * 12)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b").write_bytes(b"x" * 300)
    (tmp_path / "link").symlink_to(tmp_path / "a")
    assert sorted(benford.file_sizes(tmp_path)) == [12, 300]


@pytest.fixture
def repo(tmp_path):
    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "a.txt").write_text("hello\n\nthree lines long\n", encoding="utf-8")
    (tmp_path / "b.bin").write_bytes(b"\xff\xfe\x00")
    git("add", ".")
    git("commit", "-q", "-m", "one")
    (tmp_path / "a.txt").write_text("hello\n", encoding="utf-8")
    git("commit", "-q", "-am", "two")
    return tmp_path


def test_line_lengths_skip_empty_lines_and_binaries(repo):
    assert benford.line_lengths(repo) == [5]


def test_diff_sizes_skip_binaries(repo):
    # Commit one adds 3 lines to a.txt; commit two removes 2. Zeros are kept here.
    assert sorted(benford.diff_sizes(repo)) == [0, 0, 2, 3]


def test_table_and_svgs_from_given_data():
    rng = random.Random(1)
    datasets = [
        benford.Dataset("log-uniform", [int(10 ** rng.uniform(0, 5)) + 1 for _ in range(3000)]),
        benford.Dataset("seventies", list(range(70, 80)) * 30),
    ]
    text = benford.table(datasets)
    assert "log-uniform" in text and "seventies" in text
    assert "nonconformity" in text.splitlines()[-1]
    assert "worst MAD" in benford.sweep_table(datasets, steps=5)
    for svg in (benford.digits_svg(datasets), benford.sweep_svg(datasets, steps=5)):
        root = ET.fromstring(svg)
        assert root.tag.endswith("svg")


def test_main_rejects_unknown_source(capsys):
    with pytest.raises(SystemExit):
        benford.main(["nope"])
    assert "unknown source" in capsys.readouterr().err


def test_main_writes_pictures(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(benford.SOURCES, "fake", ("fake", lambda: [1, 2, 3, 15, 120, 0]))
    assert benford.main(["fake", "--sweep", "--out", str(tmp_path)]) == 0
    assert (tmp_path / "digits.svg").exists() and (tmp_path / "sweep.svg").exists()
    assert "fake" in capsys.readouterr().out
