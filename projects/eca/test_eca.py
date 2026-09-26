import struct
import zlib
from math import comb

import eca
import pytest


def rows_as_text(rule: int, steps: int) -> list[str]:
    width = 2 * steps + 1
    rows = eca.run(rule, eca.single_cell(width), steps, width)
    return eca.render_text(rows, width, ink="1", paper="0").split("\n")


def test_rule_30_matches_the_known_first_rows():
    # The first rows of rule 30 from a single cell, as in every textbook.
    assert rows_as_text(30, 3) == ["0001000", "0011100", "0110010", "1101111"]


def test_rule_90_is_pascals_triangle_mod_2():
    steps = 12
    width = 2 * steps + 1
    rows = eca.run(90, eca.single_cell(width), steps, width)
    for t, row in enumerate(rows):
        bits = eca.to_bits(row, width)
        for k in range(width):
            offset = k - steps  # distance from the centre
            expected = (
                comb(t, (t + offset) // 2) % 2 if (t + offset) % 2 == 0 and abs(offset) <= t else 0
            )
            assert bits[k] == expected, (t, k)


def test_shift_rules_move_the_row_by_one_cell_and_wrap():
    width = 9
    row = eca.from_bits([1, 1, 0, 1, 0, 0, 0, 0, 0])
    # Rule 170 copies the right neighbour, so the pattern moves left.
    assert eca.to_bits(eca.step(row, 170, width), width) == [1, 0, 1, 0, 0, 0, 0, 0, 1]
    # Rule 240 copies the left neighbour, so the pattern moves right.
    assert eca.to_bits(eca.step(row, 240, width), width) == [0, 1, 1, 0, 1, 0, 0, 0, 0]


def test_identity_complement_and_uniform_rules():
    width = 16
    row = eca.random_row(5, width)
    assert eca.step(row, 204, width) == row
    assert eca.step(row, 51, width) == eca.complement_row(row, width)
    assert eca.step(row, 0, width) == 0
    assert eca.step(row, 255, width) == (1 << width) - 1


def test_mirror_and_complement_are_involutions_that_commute():
    for rule in range(256):
        assert eca.mirror(eca.mirror(rule)) == rule
        assert eca.complement(eca.complement(rule)) == rule
        assert eca.mirror(eca.complement(rule)) == eca.complement(eca.mirror(rule))
    assert eca.mirror(30) == 86
    assert eca.complement(30) == 135


def test_there_are_88_equivalence_classes():
    classes = eca.equivalence_classes()
    assert len(classes) == 88
    assert sum(len(members) for members in classes) == 256
    assert eca.orbit(30) == (30, 86, 135, 149)
    assert eca.orbit(110) == (110, 124, 137, 193)
    assert eca.orbit(204) == (204,)
    assert eca.representative(193) == 110


def test_equivalent_rules_run_equivalently():
    # Running a rule from a flipped and/or inverted row gives exactly the
    # flipped and/or inverted run of its representative. This is the whole
    # justification for classifying one rule per class.
    width, steps = 31, 20
    seed = eca.random_row(9, width)
    for rule in range(256):
        rep = eca.representative(rule)
        flip, invert = eca.transform_from_representative(rule)
        expected = [
            eca.transform_row(row, width, flip, invert) for row in eca.run(rep, seed, steps, width)
        ]
        start = eca.transform_row(seed, width, flip, invert)
        assert eca.run(rule, start, steps, width) == expected, rule


def test_ring_is_prime_with_2_as_a_primitive_root():
    # On such a ring the additive rules (90, 150, 60, 105) have periods that
    # divide 2**((RING - 1) / 2) - 1, far beyond any run here. On a ring of
    # 64 cells rule 90 dies out after 32 steps and looks "uniform".
    n = eca.RING
    assert n > 2 and all(n % d for d in range(2, int(n**0.5) + 1))
    assert all(pow(2, k, n) != 1 for k in range(1, n - 1))
    width = 64
    rows = eca.run(90, eca.random_row(1, width), 32, width)
    assert rows[31] != 0
    assert rows[32] == 0


def test_single_cell_panel_fits_odd_and_even_windows():
    # The outermost cells of rule 90's cone are always black, so cropping
    # the cone would change the count.
    for window in (80, 81):
        layout = eca.Layout(window=window)
        assert 2 * (layout.single_rows - 1) + 1 <= window
        rows = eca.run(90, eca.single_cell(eca.RING), layout.single_rows - 1, eca.RING)
        assert eca.crop(rows[-1], eca.RING, window).bit_count() == rows[-1].bit_count()


def test_settle_finds_the_transient_and_the_exact_cycle():
    width = 61
    start = eca.random_row(2, width)
    rows, transient = eca.settle(51, start, 10, width)  # blinks from the first row
    assert transient == 0 and len(rows) == 3 and rows[-1] == rows[0]
    rows, transient = eca.settle(170, start, 100, width)  # a shift comes back after a lap
    assert transient == 0 and len(rows) - 1 == width
    rows, transient = eca.settle(8, start, 10, width)  # dies, then stays dead
    assert rows[-1] == rows[-2] == 0 and transient == len(rows) - 2
    rows, transient = eca.settle(30, start, 200, width)
    assert transient is None and len(rows) == 201
    assert len(set(rows)) == len(rows)


def test_measure_reports_cycles_of_any_length():
    # Rule 73's walls cut the ring into regions that cycle separately, so the
    # ring's own period is long; it used to be cut off at 64 steps and fall
    # through to the compression measure.
    m = eca.measure(73, 1)
    assert (m.transient, m.period, m.kind) == (44, 120, "periodic")
    m = eca.measure(41, 1)
    assert m.period == 1688 and m.kind == "periodic"
    m = eca.measure(30, 1)
    assert m.transient is None and m.period is None and m.kind == "chaotic"


def test_crop_takes_the_middle_window():
    row = eca.from_bits([1, 0, 1, 1, 0, 1, 0])
    assert eca.to_bits(eca.crop(row, 7, 3), 3) == [1, 1, 0]
    assert eca.crop(row, 7, 7) == row


def test_entropy_and_compression_measures():
    assert eca.binary_entropy(0.5) == 1.0
    assert eca.binary_entropy(0.0) == 0.0
    assert eca.binary_entropy(0.2) == pytest.approx(eca.binary_entropy(0.8))
    width = 101
    blank = [0] * 64
    noisy = eca.run(30, eca.random_row(1, width), 300, width)[-64:]
    assert eca.bits_per_cell(blank, width) < 0.05
    assert eca.bits_per_cell(noisy, width) > 0.9


def test_verdict_is_the_median_kind():
    def fake(kind: str) -> eca.Measure:
        return {
            "uniform": eca.Measure(0, 0, True, 3, 1, 0.0, 0.0),
            "periodic": eca.Measure(0, 0, False, 10, 2, 0.5, 0.1),
            "chaotic": eca.Measure(0, 0, False, None, None, 0.5, 1.0),
            "complex": eca.Measure(0, 0, False, None, None, 0.5, 0.5),
        }[kind]

    assert all(fake(kind).kind == kind for kind in eca.KINDS)
    assert eca.verdict([fake("uniform"), fake("chaotic"), fake("periodic")]) == "periodic"
    assert eca.verdict([fake("complex"), fake("chaotic"), fake("chaotic")]) == "chaotic"


def test_classification_of_famous_rules():
    classes = eca.classify_all()
    assert len(classes) == 256
    for members in eca.equivalence_classes():
        assert len({classes[rule] for rule in members}) == 1
    by_kind = {kind: {rule for rule, k in classes.items() if k == kind} for kind in eca.KINDS}
    assert {0, 8, 32, 128, 255} <= by_kind["uniform"]
    assert {2, 4, 41, 51, 62, 73, 108, 170, 184, 204} <= by_kind["periodic"]
    assert {30, 45, 90, 105, 150} <= by_kind["chaotic"]
    assert {54, 110} <= by_kind["complex"]


def test_png_is_well_formed():
    data = eca.png([0b101, 0b010], 3, ink="#000000", paper="#ffffff")
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    pos = 8
    chunks = {}
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        tag = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        (crc,) = struct.unpack(">I", data[pos + 8 + length : pos + 12 + length])
        assert crc == zlib.crc32(tag + body) & 0xFFFFFFFF, tag
        chunks[tag] = body
        pos += 12 + length
    assert list(chunks) == [b"IHDR", b"PLTE", b"IDAT", b"IEND"]
    assert struct.unpack(">IIBBBBB", chunks[b"IHDR"]) == (3, 2, 1, 3, 0, 0, 0)
    assert chunks[b"PLTE"] == bytes.fromhex("ffffff000000")
    assert zlib.decompress(chunks[b"IDAT"]) == bytes([0, 0b10100000, 0, 0b01000000])


def test_poster_shows_every_rule_once():
    classes = eca.classify_all()
    svg = eca.poster(classes, eca.Layout(window=41, random_rows=16))
    assert svg.startswith("<svg ")
    assert svg.rstrip().endswith("</svg>")
    for rule in range(256):
        assert svg.count(f'id="rule-{rule}"') == 1
    assert svg.count("<image ") == 512
    for kind in eca.KINDS:
        assert kind.capitalize() in svg


def test_summary_counts_add_up():
    classes = eca.classify_all()
    text = eca.summary(classes)
    counts = [int(line.split(":")[1].split()[0]) for line in text.splitlines() if ":" in line]
    assert sum(counts) == 256


def test_cli_prints_a_rule_as_text(capsys):
    assert eca.main(["--rule", "30", "--steps", "3"]) == 0
    out = capsys.readouterr().out.rstrip("\n").split("\n")
    assert out == ["...#...", "..###..", ".##..#.", "##.####"]
    with pytest.raises(SystemExit):
        eca.main(["--rule", "256"])


def test_cli_writes_the_poster(tmp_path):
    out = tmp_path / "poster.svg"
    for bad in ("0", "-5", str(eca.RING + 1)):
        with pytest.raises(SystemExit):
            eca.main(["--out", str(out), "--window", bad])
    assert not out.exists()
    assert eca.main(["--out", str(out), "--window", "21"]) == 0
    assert out.read_text(encoding="utf-8").startswith("<svg ")
    assert out.stat().st_size < 400_000
