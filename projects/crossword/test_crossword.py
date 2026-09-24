from pathlib import Path

import crossword as cw
import pytest

HERE = Path(__file__).parent

SMALL = """
# a tiny themed list
COOPER | the agent
LAURA | the queen
DONNA | the friend
PETE | the fisherman
LOG LADY | the log's keeper
ANDY | the deputy
"""


@pytest.fixture(scope="module")
def twin_peaks() -> cw.Puzzle:
    entries = cw.parse_entries(cw.DEFAULT_WORDS.read_text(encoding="utf-8"))
    puzzle, _seed = cw.best_build(entries)
    return puzzle


def grid_from(word: str, row: int = 0, col: int = 0, across: bool = True) -> dict[cw.Cell, str]:
    p = cw.Placement(cw.Entry(word, "x"), row, col, across)
    return dict(zip(p.cells, word, strict=True))


# ---------------------------------------------------------------- entries


def test_enumeration_counts_letters_and_marks_word_breaks():
    assert cw.Entry("COOPER", "").enumeration == "(6)"
    assert cw.Entry("LOG LADY", "").enumeration == "(3,4)"
    assert cw.Entry("ONE-ARMED", "").enumeration == "(3-5)"
    assert cw.Entry("FIRE WALK WITH ME", "").enumeration == "(4,4,4,2)"
    assert cw.Entry("Double R", "").enumeration == "(6,1)"
    assert cw.Entry("DON'T", "").enumeration == "(4)"
    assert cw.Entry("Log Lady", "").letters == "LOGLADY"


def test_parse_entries_skips_comments_and_blank_lines():
    entries = cw.parse_entries(SMALL)
    assert [e.letters for e in entries] == ["COOPER", "LAURA", "DONNA", "PETE", "LOGLADY", "ANDY"]
    assert entries[4].answer == "LOG LADY"
    assert entries[4].clue == "the log's keeper"


@pytest.mark.parametrize(
    "line",
    [
        "COOPER the agent",
        "R2D2 | droid",
        "A | one letter",
        "COOPER | agent\nCooper | again",
        "COOPER |",
    ],
)
def test_parse_entries_rejects_bad_lines(line):
    with pytest.raises(ValueError):
        cw.parse_entries(line)


# ---------------------------------------------------------------- placing


def test_fit_counts_crossings_and_refuses_what_would_misread():
    cells = grid_from("LAURA")
    # AUDREY down through the A of LAURA: one crossing.
    assert cw.fit(cells, "AUDREY", 0, 1, False) == 1
    # DONNA down through the same cell: D is not A.
    assert cw.fit(cells, "DONNA", 0, 1, False) is None
    # PETE down starting right under the U: it would run on from LAURA's U.
    assert cw.fit(cells, "PETE", 1, 2, False) is None
    # PETE across on the row below: every letter would touch one above it.
    assert cw.fit(cells, "PETE", 1, 0, True) is None
    # PETE across ending just before the L: it would run into LAURA.
    assert cw.fit(cells, "PETE", 0, -4, True) is None
    # LAURA on top of itself adds nothing.
    assert cw.fit(cells, "LAURA", 0, 0, True) is None
    # A word lying along another in the same direction is not a crossing:
    # the reviewer found BOB inside BOBBY placed this way on a few seeds.
    assert cw.fit(grid_from("BOB"), "BOBBY", 0, 0, True) is None
    assert cw.fit(grid_from("ANDY"), "CANDY", 0, -1, True) is None
    assert cw.fit(grid_from("ANDY", 0, 0, False), "CANDY", -1, 0, False) is None
    # Far away: legal in itself, but no crossing, which build() refuses.
    assert cw.fit(cells, "PETE", 3, 0, True) == 0


def test_fit_allows_a_word_through_a_crossing_on_a_fresh_row():
    # ANDY down through LAURA's A, then DONNA across through ANDY's D: the D
    # is a crossing and DONNA's other letters have nothing above or below.
    cells = grid_from("LAURA")
    cells.update(grid_from("ANDY", 0, 1, False))
    assert cw.fit(cells, "DONNA", 2, 1, True) == 1
    # One row up, its O, N, N, A would sit right under LAURA's letters.
    assert cw.fit(cells, "DONNA", 1, 1, True) is None


def test_build_reads_back_exactly_the_placed_words():
    # Every maximal run of two or more letters in the grid must be one of the
    # placed answers, and every placed answer must be such a run.
    # Every seed the default search looks at, since seeds 107, 116, 134 and
    # 178 once laid BOB along BOBBY and a sweep of six never saw it.
    for text in (SMALL, cw.DEFAULT_WORDS.read_text(encoding="utf-8")):
        entries = cw.parse_entries(text)
        for seed in range(cw.DEFAULT_TRIES):
            puzzle = cw.build(entries, seed)
            placed = {((p.row, p.col), p.across, p.entry.letters) for p in puzzle.placements}
            assert set(cw.runs(puzzle.cells)) == placed, seed
            assert len(placed) == len(puzzle.placements)


def test_every_answer_after_the_first_crosses_another():
    entries = cw.parse_entries(cw.DEFAULT_WORDS.read_text(encoding="utf-8"))
    puzzle = cw.build(entries, 1)
    counts: dict[cw.Cell, int] = {}
    for p in puzzle.placements:
        for cell in p.cells:
            counts[cell] = counts.get(cell, 0) + 1
    assert all(any(counts[c] > 1 for c in p.cells) for p in puzzle.placements)


def test_numbering_is_row_major_and_shared_between_across_and_down():
    entries = cw.parse_entries(cw.DEFAULT_WORDS.read_text(encoding="utf-8"))
    puzzle = cw.build(entries, 2)
    starts = sorted({(p.row, p.col) for p in puzzle.placements})
    numbers = {(p.row, p.col): p.number for p in puzzle.placements}
    assert [numbers[s] for s in starts] == list(range(1, len(starts) + 1))
    for p in puzzle.placements:
        assert p.number == numbers[(p.row, p.col)]
    assert [p.number for p in puzzle.placements] == sorted(p.number for p in puzzle.placements)
    shared = [s for s in starts if sum(1 for p in puzzle.placements if (p.row, p.col) == s) == 2]
    assert shared, "expected at least one cell that starts both an across and a down answer"


def test_grid_starts_at_the_origin_and_respects_max_size():
    entries = cw.parse_entries(cw.DEFAULT_WORDS.read_text(encoding="utf-8"))
    for seed in range(4):
        puzzle = cw.build(entries, seed, max_size=15)
        cells = puzzle.cells
        assert min(r for r, _ in cells) == 0 and min(c for _, c in cells) == 0
        assert puzzle.rows <= 15 and puzzle.cols <= 15
        assert puzzle.rows == max(r for r, _ in cells) + 1
        assert puzzle.cols == max(c for _, c in cells) + 1


def test_a_tiny_grid_leaves_long_answers_out():
    entries = cw.parse_entries(SMALL)
    puzzle = cw.build(entries, 0, max_size=5)
    assert puzzle.rows <= 5 and puzzle.cols <= 5
    # The first answer is placed without a crossing, but not without the cap.
    assert cw.Entry("LOG LADY", "the log's keeper") in puzzle.unplaced
    assert cw.Entry("COOPER", "the agent") in puzzle.unplaced
    assert len(puzzle.placements) >= 2


def test_a_first_word_nothing_can_cross_is_swapped_out():
    # The review bot pointed out that the first word goes in without a
    # crossing, so a word that shares no letter with the rest used to sit
    # alone in the grid and block every other answer.
    entries = [
        cw.Entry("ZZZZZZZZZZ", "z"),
        cw.Entry("LAURA", "a"),
        cw.Entry("ANDY", "b"),
        cw.Entry("DONNA", "c"),
    ]
    for seed in range(5):
        puzzle = cw.build(entries, seed)
        placed = {p.entry.letters for p in puzzle.placements}
        assert "ZZZZZZZZZZ" not in placed and len(placed) >= 2, seed
        assert cw.Entry("ZZZZZZZZZZ", "z") in puzzle.unplaced
        assert puzzle.crossings >= 1


def test_one_entry_gives_a_one_word_grid():
    puzzle = cw.build([cw.Entry("COOPER", "x")], 0)
    assert [p.entry.letters for p in puzzle.placements] == ["COOPER"]
    assert puzzle.unplaced == []
    assert puzzle.crossings == 0 and "0 crossings" in puzzle.summary()


def test_first_answer_is_the_longest_and_lands_across():
    entries = cw.parse_entries(SMALL)
    puzzle = cw.build(entries, 3)
    log_lady = next(p for p in puzzle.placements if p.entry.letters == "LOGLADY")
    assert log_lady.across


def test_same_seed_same_puzzle_and_seeds_differ():
    entries = cw.parse_entries(SMALL)
    assert cw.build(entries, 5) == cw.build(entries, 5)
    layouts = {tuple(sorted(cw.build(entries, s).cells.items())) for s in range(10)}
    assert len(layouts) > 1


def test_best_build_prefers_more_letters_then_crossings():
    entries = cw.parse_entries(SMALL)
    best, seed = cw.best_build(entries, tries=12, max_size=8)
    assert 0 <= seed < 12
    for s in range(12):
        other = cw.build(entries, s, max_size=8)
        key = lambda p: (sum(len(q.entry.letters) for q in p.placements), p.crossings)  # noqa: E731
        assert key(other) <= key(best)


def test_empty_list_builds_an_empty_puzzle():
    puzzle, _ = cw.best_build([], tries=1)
    assert puzzle.placements == [] and puzzle.rows == 0 and puzzle.cols == 0
    assert "0 of 0" in puzzle.summary()
    assert cw.render_svg(puzzle).startswith("<svg ")


# ---------------------------------------------------------------- the puzzle


def test_twin_peaks_places_every_entry(twin_peaks):
    assert twin_peaks.unplaced == []
    assert len(twin_peaks.placements) == 39
    assert twin_peaks.rows <= cw.DEFAULT_MAX_SIZE and twin_peaks.cols <= cw.DEFAULT_MAX_SIZE


def test_committed_outputs_match_the_code(twin_peaks):
    hint = "regenerate: python projects/crossword/crossword.py --out-dir projects/crossword/out"
    puzzle_svg = (HERE / "out" / "twin-peaks.svg").read_text(encoding="utf-8")
    assert puzzle_svg == cw.render_svg(twin_peaks), hint
    solution_svg = (HERE / "out" / "twin-peaks-solution.svg").read_text(encoding="utf-8")
    assert solution_svg == cw.render_svg(twin_peaks, solution=True, clues=False), hint


def test_readme_lists_the_puzzle_clues(twin_peaks):
    readme = (HERE / "README.md").read_text(encoding="utf-8")
    assert cw.render_markdown(twin_peaks) in readme


# ---------------------------------------------------------------- rendering


def test_wrap_keeps_lines_within_width_and_loses_nothing():
    text = "Rosenfield, FBI forensics, rude to everyone and a pacifist in his own words (6)"
    lines = cw.wrap(text, 30)
    assert all(len(line) <= 30 for line in lines)
    assert " ".join(lines) == text
    assert len(lines) == 3
    assert cw.wrap("supercalifragilistic word", 5) == ["supercalifragilistic", "word"]
    assert cw.wrap("", 10) == []


def test_svg_has_a_cell_per_letter_and_letters_only_in_the_solution():
    entries = cw.parse_entries(SMALL)
    puzzle = cw.build(entries, 0)
    blank = cw.render_svg(puzzle, "Test")
    filled = cw.render_svg(puzzle, "Test", solution=True, clues=False)
    for svg in (blank, filled):
        assert svg.startswith("<svg ") and svg.rstrip().endswith("</svg>")
        assert svg.count("<rect ") == len(puzzle.cells) + 1  # plus the background
    assert blank.count('text-anchor="middle"') == 0
    assert filled.count('text-anchor="middle"') == len(puzzle.cells)
    assert blank.count("<tspan ") >= len(puzzle.placements)
    assert "<tspan " not in filled
    assert "the log&#x27;s keeper (3,4)" in blank


def test_text_rendering_shows_the_grid_and_clues():
    entries = cw.parse_entries(SMALL)
    puzzle = cw.build(entries, 0)
    blank = cw.render_text(puzzle)
    filled = cw.render_text(puzzle, solution=True)
    grid = blank.splitlines()[: puzzle.rows]
    assert all(len(row) == puzzle.cols for row in grid)
    assert sum(row.count("#") for row in grid) == len(puzzle.cells)
    assert "[LOGLADY]" in filled and "[LOGLADY]" not in blank
    assert "Across" in blank and "Down" in blank


def test_markdown_has_one_line_per_answer():
    entries = cw.parse_entries(SMALL)
    puzzle = cw.build(entries, 0)
    md = cw.render_markdown(puzzle)
    assert md.count("\n- **") == len(puzzle.placements)
    assert md.startswith("**Across**\n")


def test_cli_writes_puzzle_and_solution(tmp_path, capsys):
    words = tmp_path / "small_list.txt"
    words.write_text(SMALL, encoding="utf-8")
    out = tmp_path / "out"
    assert cw.main(["--words", str(words), "--out-dir", str(out), "--seed", "1", "--text"]) == 0
    assert (out / "small-list.svg").read_text().startswith("<svg ")
    assert (out / "small-list-solution.svg").read_text().startswith("<svg ")
    assert ">small-list<" in (out / "small-list.svg").read_text()
    captured = capsys.readouterr()
    assert "Across" in captured.out
    assert captured.err.startswith("seed 1, ")


def test_cli_rejects_bad_numbers():
    with pytest.raises(SystemExit):
        cw.main(["--tries", "0"])
