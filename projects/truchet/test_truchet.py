import itertools
import math
import re
from pathlib import Path

import pytest
import truchet

OUT = Path(__file__).parent / "out"


def test_same_seed_same_output():
    a = truchet.render_svg(truchet.generate(12, 3))
    b = truchet.render_svg(truchet.generate(12, 3))
    assert a == b


def test_different_seeds_differ():
    assert truchet.generate(12, 1).tiles != truchet.generate(12, 2).tiles


def test_every_tile_contributes_two_arcs():
    t = truchet.generate(9, 5)
    assert len(t.arcs) == 2 * 9 * 9
    assert sum(t.lengths) == len(t.arcs)


def test_open_paths_is_always_two_n():
    # Every edge midpoint on the border ends exactly one path, and there are
    # 4n of them, so an n x n grid always has 2n border-to-border paths.
    for n in (1, 2, 5, 16):
        for seed in range(5):
            t = truchet.generate(n, seed)
            assert t.open_path_count == 2 * n, (n, seed)


def path_ends(t: truchet.Tiling) -> dict[int, list[truchet.Node]]:
    """The border nodes of each open path, by path id."""
    ends: dict[int, list[truchet.Node]] = {}
    for arc in t.arcs:
        nodes = truchet.tile_nodes(arc.row, arc.col)
        for edge in (arc.a, arc.b):
            if truchet.is_boundary(nodes[edge], t.n):
                ends.setdefault(arc.path_id, []).append(nodes[edge])
    return ends


def test_paths_have_zero_or_two_border_ends():
    t = truchet.generate(10, 11)
    ends = path_ends(t)
    assert all(len(nodes) == 2 for nodes in ends.values())
    assert len(ends) == t.open_path_count
    assert all(t.loops[pid] == (pid not in ends) for pid in range(t.path_count))


def border_of(node: truchet.Node, n: int) -> str:
    kind, r, c = node
    if kind == "h":
        return "top" if r == 0 else "bottom"
    return "left" if c == 0 else "right"


def test_length_mod_four_says_which_borders_a_path_joins():
    # Consecutive arcs of a path share an edge midpoint, so their tiles are
    # neighbours across that edge. Every arc joins a horizontal-edge midpoint
    # to a vertical-edge midpoint, so the shared midpoints alternate between
    # the two kinds along the path, and the moves from tile to tile alternate
    # vertical, horizontal, vertical, ... A closed loop of k arcs makes k
    # moves, half of them vertical, and those must net to zero, so k/2 is
    # even: every loop has a multiple of four arcs. An open path of k arcs
    # makes k - 1 moves; counting which of them are vertical gives the rest.
    opposite = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}
    seen = set()
    for n in (3, 4, 8, 9, 16):
        for seed in range(6):
            t = truchet.generate(n, seed)
            ends = path_ends(t)
            for pid, k in enumerate(t.lengths):
                if t.loops[pid]:
                    assert k % 4 == 0, (n, seed, pid, k)
                    continue
                a, b = (border_of(node, n) for node in ends[pid])
                if a == b:
                    assert k % 4 == 2, (n, seed, pid, k, a)
                    seen.add("same")
                elif b == opposite[a]:
                    assert k % 4 == (2 * n) % 4, (n, seed, pid, k, a, b)
                    seen.add("opposite")
                else:
                    assert k % 2 == 1, (n, seed, pid, k, a, b)
                    seen.add("adjacent")
    assert seen == {"same", "opposite", "adjacent"}


def test_single_tile_has_two_open_paths_and_no_loops():
    t = truchet.generate(1, 0)
    assert t.path_count == 2
    assert t.loop_count == 0
    assert t.lengths == [1, 1]
    assert truchet.touching_pairs(t) == {(0, 1)}


def loop_forming_two_by_two() -> truchet.Tiling:
    # Tiles 1 0 / 0 1 close a ring around the centre point.
    for seed in range(200):
        t = truchet.generate(2, seed)
        if t.tiles == [[1, 0], [0, 1]]:
            return t
    raise AssertionError("expected to hit the loop-forming 2x2 layout within 200 seeds")


def test_two_by_two_can_form_a_loop():
    t = loop_forming_two_by_two()
    assert t.loop_count == 1
    assert t.path_count == 5
    # First appearance numbers the top-left corner nub 0 and the loop 1; the
    # loop has four arcs and touches each of the four corner nubs.
    assert t.loops == [False, True, False, False, False]
    assert t.lengths == [1, 4, 1, 1, 1]
    assert truchet.touching_pairs(t) == {(0, 1), (1, 2), (1, 3), (1, 4)}


def test_touching_pairs_are_exactly_the_paths_sharing_a_tile():
    t = truchet.generate(7, 4)
    expected = set()
    for first, second in zip(t.arcs[0::2], t.arcs[1::2], strict=True):
        assert (first.row, first.col) == (second.row, second.col)
        if first.path_id != second.path_id:
            expected.add(tuple(sorted((first.path_id, second.path_id))))
    assert truchet.touching_pairs(t) == expected
    assert all(a < b for a, b in expected)


def test_palette_distance_is_cyclic():
    assert truchet.palette_distance(0, 11, 12) == 1
    assert truchet.palette_distance(3, 9, 12) == 6
    assert truchet.palette_distance(5, 5, 12) == 0
    assert truchet.palette_distance(11, 1, 12) == 2


def test_touching_paths_are_kept_apart_where_avoidable():
    # Each path, in order, must take a color two steps clear of every path
    # it touches that was colored before it, whenever such a color exists;
    # and one step clear (a different color) whenever that exists. Across
    # these seeds no two touching paths ever share a color.
    size = len(truchet.PALETTE)
    forced = 0
    for n in (4, 8, 16, 24):
        for seed in range(10):
            t = truchet.generate(n, seed)
            chosen = truchet.assign_palette(t)
            assert len(chosen) == t.path_count
            neighbours: list[set[int]] = [set() for _ in range(t.path_count)]
            for a, b in truchet.touching_pairs(t):
                neighbours[a].add(b)
                neighbours[b].add(a)
            for pid, k in enumerate(chosen):
                earlier = {chosen[q] for q in neighbours[pid] if q < pid}
                gap = min((truchet.palette_distance(k, c, size) for c in earlier), default=size)
                clear = [
                    x
                    for x in range(size)
                    if all(truchet.palette_distance(x, c, size) >= 2 for c in earlier)
                ]
                if clear:
                    assert gap >= 2, (n, seed, pid)
                else:
                    forced += 1
                    assert gap >= 1 or len(earlier) == size, (n, seed, pid)
            for a, b in truchet.touching_pairs(t):
                assert chosen[a] != chosen[b], (n, seed, a, b)
    # The rule is nearly always satisfiable; a handful of hemmed-in paths per
    # forty tilings have to settle for one step.
    assert forced < 20


def test_palette_is_used_evenly():
    t = truchet.generate(24, 7)
    counts = [0] * len(truchet.PALETTE)
    for k in truchet.assign_palette(t):
        counts[k] += 1
    assert min(counts) >= 1
    assert max(counts) - min(counts) <= 2


def test_length_bucket_is_floor_log2_capped():
    assert [truchet.length_bucket(m) for m in (1, 2, 3, 4, 7, 8, 15, 16)] == [
        0,
        1,
        1,
        2,
        2,
        3,
        3,
        4,
    ]
    assert truchet.length_bucket(2**11) == 11
    assert truchet.length_bucket(10**6) == len(truchet.LENGTH_RAMP) - 1
    with pytest.raises(ValueError):
        truchet.length_bucket(0)


def test_length_colors_depend_only_on_length():
    t = truchet.generate(16, 3)
    colors = truchet.path_colors(t, "length")
    by_length: dict[int, set[str]] = {}
    for m, color in zip(t.lengths, colors, strict=True):
        by_length.setdefault(m, set()).add(color)
    assert all(len(shades) == 1 for shades in by_length.values())
    assert by_length[4] == {truchet.LENGTH_RAMP[2]}
    assert by_length[max(t.lengths)] != by_length[min(t.lengths)]
    with pytest.raises(ValueError):
        truchet.path_colors(t, "hue")


def test_svg_has_one_element_per_path_and_valid_header():
    t = truchet.generate(6, 2)
    svg = truchet.render_svg(t)
    assert svg.startswith("<svg ")
    assert svg.count("<path ") == t.path_count
    assert svg.count(" A") == len(t.arcs)
    assert svg.rstrip().endswith("</svg>")


def test_chains_walk_every_arc_once_end_to_start():
    for n, seed in ((1, 0), (2, 4), (7, 1), (16, 3)):
        t = truchet.generate(n, seed)
        chains = truchet.chain_paths(t)
        assert len(chains) == t.path_count
        walked = [arc for steps in chains for arc, _, _ in steps]
        assert len(walked) == len(t.arcs) and set(walked) == set(t.arcs)
        for pid, steps in enumerate(chains):
            assert len(steps) == t.lengths[pid]
            assert all(arc.path_id == pid for arc, _, _ in steps)
            # Each step is one of its arc's two ends to the other.
            assert all({a, b} == {arc.a, arc.b} for arc, a, b in steps)
            ends = [
                (truchet.tile_nodes(arc.row, arc.col)[a], truchet.tile_nodes(arc.row, arc.col)[b])
                for arc, a, b in steps
            ]
            for (_, end), (start, _) in itertools.pairwise(ends):
                assert end == start, (n, seed, pid)
            first, last = ends[0][0], ends[-1][1]
            if t.loops[pid]:
                assert first == last
            else:
                assert truchet.is_boundary(first, n) and truchet.is_boundary(last, n)
                assert first < last  # starts at the smaller border midpoint


def test_svg_paths_are_single_strokes_and_loops_close():
    t = truchet.generate(12, 5)
    svg = truchet.render_svg(t)
    ds = re.findall(r'<path d="([^"]*)"', svg)
    assert len(ds) == t.path_count
    for pid, d in enumerate(ds):
        assert d.count("M") == 1 and d.startswith("M")
        assert d.count("A") == t.lengths[pid]
        assert d.endswith(" Z") == t.loops[pid]
        if t.loops[pid]:
            # The last arc lands back on the starting point.
            start = d[1:].split(" ")[0]
            last_end = d.split(" ")[-2]
            assert start == last_end


def test_bucket_labels_name_each_ramps_range():
    assert [truchet.bucket_label(k) for k in range(4)] == ["1", "2–3", "4–7", "8–15"]
    assert truchet.bucket_label(len(truchet.LENGTH_RAMP) - 1) == "2048+"


def test_length_mode_draws_a_legend_up_to_the_longest_path():
    t = truchet.generate(10, 4)
    plain = truchet.render_svg(t)
    length = truchet.render_svg(t, color="length")
    assert "<text" not in plain
    assert 'height="320"' in plain and 'height="380.8"' in length
    shown = truchet.length_bucket(max(t.lengths)) + 1
    labels = re.findall(r"<text [^>]*>([^<]*)</text>", length)
    assert labels == [truchet.bucket_label(k) for k in range(shown)] + ["arcs per path"]
    for k in range(shown):
        assert f'fill="{truchet.LENGTH_RAMP[k]}"' in length
    assert f'fill="{truchet.LENGTH_RAMP[shown]}"' not in length


def test_loops_only_dims_exactly_the_open_paths():
    t = truchet.generate(12, 5)
    assert t.loop_count > 0
    svg = truchet.render_svg(t, loops_only=True)
    assert svg.count(f'stroke="{truchet.DIM}"') == t.open_path_count
    colors = truchet.path_colors(t)
    for pid, color in enumerate(colors):
        if t.loops[pid]:
            assert f'stroke="{color}"' in svg
    plain = truchet.render_svg(t)
    assert truchet.DIM not in plain


def test_sweep_flag_for_north_east_arc():
    # Arc from the north midpoint to the east midpoint, centred on the
    # north-east corner, runs counter-clockwise on screen: sweep flag 0.
    s = 10.0
    start = truchet.midpoint("N", 0, 0, s)
    end = truchet.midpoint("E", 0, 0, s)
    center = truchet.corner("N", "E", 0, 0, s)
    assert center == (10.0, 0.0)
    assert truchet.sweep_flag(start, end, center) == 0


def test_arcs_are_centred_on_corners_not_tile_centre():
    # For each arc, both endpoints lie on the circle of radius r around the
    # corner the arc is drawn about.
    s = 10.0
    r = s / 2
    for kind in (0, 1):
        for a, b in truchet.tile_arcs(kind):
            cx, cy = truchet.corner(a, b, 0, 0, s)
            sx, sy = truchet.midpoint(a, 0, 0, s)
            ex, ey = truchet.midpoint(b, 0, 0, s)
            assert math.isclose(math.dist((sx, sy), (cx, cy)), r)
            assert math.isclose(math.dist((ex, ey), (cx, cy)), r)


def test_cli_writes_file(tmp_path, capsys):
    out = tmp_path / "x.svg"
    assert truchet.main(["--size", "4", "--seed", "1", "--out", str(out)]) == 0
    assert out.read_text().startswith("<svg ")
    assert "4x4 seed 1:" in capsys.readouterr().err


def test_cli_modes(tmp_path):
    plain = tmp_path / "plain.svg"
    length = tmp_path / "length.svg"
    loops = tmp_path / "loops.svg"
    base = ["--size", "8", "--seed", "2"]
    assert truchet.main([*base, "--out", str(plain)]) == 0
    assert truchet.main([*base, "--color", "length", "--out", str(length)]) == 0
    assert truchet.main([*base, "--loops-only", "--out", str(loops)]) == 0
    assert len({plain.read_text(), length.read_text(), loops.read_text()}) == 3
    assert truchet.DIM in loops.read_text()
    with pytest.raises(SystemExit):
        truchet.main([*base, "--color", "hue"])


def test_torus_uses_the_same_tiles_and_closes_every_path():
    # Gluing the edges joins the 2n open paths end to end, so the torus has
    # every flat loop plus whatever loops the open paths become.
    for seed in range(5):
        flat = truchet.generate(8, seed)
        torus = truchet.torus_loop_lengths(8, seed)
        assert sum(torus) == len(flat.arcs)
        remaining = list(torus)
        for m, loop in zip(flat.lengths, flat.loops, strict=True):
            if loop:
                remaining.remove(m)  # every flat loop survives unchanged
        assert remaining  # and the open paths close up into at least one more
    with pytest.raises(ValueError):
        truchet.torus_loop_lengths(7, 0)


def test_torus_two_by_two_all_one_type():
    # Four tiles of type 0 on a 2x2 torus: each tile's NE arc and its SW arc
    # belong to diagonal staircases that wrap around, two of them, 4 arcs each.
    import random

    for seed in range(200):
        rng = random.Random(seed)
        if all(rng.randrange(2) == 0 for _ in range(4)):
            assert sorted(truchet.torus_loop_lengths(2, seed)) == [4, 4]
            break
    else:
        pytest.fail("no all-type-0 seed found")


def test_census_counts_add_up():
    c = truchet.loop_census(12, 5)
    assert c.seeds == 5 and c.tiles == 5 * 144
    loops = sum(round(x * 144) for x in c.loops_per_tile)
    assert sum(c.by_bucket.values()) == loops
    assert c.by_bucket[2] == sum(round(x * 144) for x in c.smallest_per_tile)
    assert min(c.by_bucket) == 2  # the smallest loop has 4 arcs
    assert len(c.torus_per_tile) == 5
    assert truchet.loop_census(7, 2).torus_per_tile == []
    with pytest.raises(ValueError):
        truchet.loop_census(12, 0)


def test_smallest_loops_average_one_per_sixteen_interior_points():
    # A 4-arc loop circles one interior grid point, and needs each of the four
    # tiles around it to turn an arc towards that point: probability 1/16.
    n, seeds = 16, 400
    c = truchet.loop_census(n, seeds)
    mean, err = truchet.mean_and_error(c.smallest_per_tile)
    expected = (n - 1) ** 2 / (16 * n * n)
    assert abs(mean - expected) < 5 * err


def test_torus_loop_density_is_near_the_bulk_value():
    # On a torus there is no border to open loops up, so at n = 32 the
    # density is already within its sampling error of (3√3 − 5)/2; the
    # finite-size excess (about 0.0008 here) is smaller than that error.
    c = truchet.loop_census(32, 32)
    mean, err = truchet.mean_and_error(c.torus_per_tile)
    assert abs(mean - truchet.BULK_LOOP_DENSITY) < 3 * err
    flat, _ = truchet.mean_and_error(c.loops_per_tile)
    assert flat < mean  # the border turns loops into open paths


def test_mean_and_error():
    assert truchet.mean_and_error([2.0]) == (2.0, 0.0)
    mean, err = truchet.mean_and_error([1.0, 2.0, 3.0])
    assert mean == 2.0 and math.isclose(err, 1 / math.sqrt(3))


def test_cli_census(capsys):
    assert truchet.main(["--size", "8", "--census", "3"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("loops in 3 tilings of 8x8 (seeds 0-2)")
    assert "on a torus" in out and "4–7" in out
    with pytest.raises(SystemExit):
        truchet.main(["--size", "8", "--census", "0"])


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("seed-7.svg", ["--size", "24", "--seed", "7"]),
        ("seed-3.svg", ["--size", "16", "--seed", "3", "--tile", "40"]),
        ("seed-7-length.svg", ["--size", "24", "--seed", "7", "--color", "length"]),
        ("seed-7-loops.svg", ["--size", "24", "--seed", "7", "--loops-only"]),
    ],
)
def test_committed_samples_match_the_code(tmp_path, name, args):
    out = tmp_path / name
    assert truchet.main([*args, "--out", str(out)]) == 0
    assert out.read_text() == (OUT / name).read_text()
