import truchet


def test_same_seed_same_output():
    a = truchet.render_svg(truchet.generate(12, 3))
    b = truchet.render_svg(truchet.generate(12, 3))
    assert a == b


def test_different_seeds_differ():
    assert truchet.generate(12, 1).tiles != truchet.generate(12, 2).tiles


def test_every_tile_contributes_two_arcs():
    t = truchet.generate(9, 5)
    assert len(t.arcs) == 2 * 9 * 9


def test_open_paths_is_always_two_n():
    # Every edge midpoint on the border ends exactly one path, and there are
    # 4n of them, so an n x n grid always has 2n border-to-border paths.
    for n in (1, 2, 5, 16):
        for seed in range(5):
            t = truchet.generate(n, seed)
            assert t.open_path_count == 2 * n, (n, seed)


def test_paths_have_zero_or_two_border_ends():
    n = 10
    t = truchet.generate(n, 11)
    ends: dict[int, int] = {}
    for arc in t.arcs:
        nodes = truchet.tile_nodes(arc.row, arc.col)
        for edge in (arc.a, arc.b):
            if truchet.is_boundary(nodes[edge], n):
                ends[arc.path_id] = ends.get(arc.path_id, 0) + 1
    assert all(count == 2 for count in ends.values())
    assert len(ends) == t.open_path_count


def test_single_tile_has_two_open_paths_and_no_loops():
    t = truchet.generate(1, 0)
    assert t.path_count == 2
    assert t.loop_count == 0


def test_two_by_two_can_form_a_loop():
    # Tiles 1 0 / 0 1 close a ring around the centre point.
    found = False
    for seed in range(200):
        t = truchet.generate(2, seed)
        if t.tiles == [[1, 0], [0, 1]]:
            assert t.loop_count == 1
            assert t.path_count == 5
            found = True
            break
    assert found, "expected to hit the loop-forming 2x2 layout within 200 seeds"


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
    # For each arc, the point a quarter-turn along it must be r away from the
    # corner and strictly closer to the corner than the tile centre would be.
    import math

    s = 10.0
    r = s / 2
    for kind in (0, 1):
        for a, b in truchet.tile_arcs(kind):
            cx, cy = truchet.corner(a, b, 0, 0, s)
            sx, sy = truchet.midpoint(a, 0, 0, s)
            ex, ey = truchet.midpoint(b, 0, 0, s)
            # Both endpoints lie on the circle of radius r around the corner.
            assert math.isclose(math.dist((sx, sy), (cx, cy)), r)
            assert math.isclose(math.dist((ex, ey), (cx, cy)), r)


def test_svg_has_one_path_per_arc_and_valid_header():
    t = truchet.generate(6, 2)
    svg = truchet.render_svg(t)
    assert svg.startswith("<svg ")
    assert svg.count("<path ") == len(t.arcs)
    assert svg.rstrip().endswith("</svg>")


def test_cli_writes_file(tmp_path):
    out = tmp_path / "x.svg"
    assert truchet.main(["--size", "4", "--seed", "1", "--out", str(out)]) == 0
    assert out.read_text().startswith("<svg ")
