import os
import subprocess
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta, timezone

import commitclock
import pytest

SVG = "{http://www.w3.org/2000/svg}"


def at(text):
    return datetime.fromisoformat(text)


@pytest.fixture
def repo(tmp_path):
    """A throwaway repository with four commits at known times and zones."""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_path, env=env, check=True)
    dates = [
        "2026-09-24T23:30:00-04:00",  # Thursday evening at -4: Friday 03:30 UTC
        "2026-09-25T23:10:00-04:00",  # Friday evening: Saturday 03:10 UTC
        "2026-09-26T03:45:00+00:00",  # Saturday 03:45 UTC
        "2026-09-28T09:00:00+05:30",  # Monday 09:00 at +5:30: Monday 03:30 UTC
    ]
    for i, date in enumerate(dates):
        (tmp_path / "f").write_text(str(i))
        subprocess.run(["git", "add", "f"], cwd=tmp_path, env=env, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", str(i)],
            cwd=tmp_path,
            env={**env, "GIT_COMMITTER_DATE": date, "GIT_AUTHOR_DATE": date},
            check=True,
        )
    return tmp_path, [at(d) for d in dates]


# --- reading and counting ---------------------------------------------------


def test_commit_times_reads_every_commit_with_its_zone(repo):
    path, dates = repo
    times = commitclock.commit_times(path)
    assert times == dates[::-1]
    assert [t.utcoffset() for t in times] == [d.utcoffset() for d in dates[::-1]]


def test_commit_times_reports_a_bad_ref(repo):
    path, _ = repo
    with pytest.raises(RuntimeError, match="git log failed"):
        commitclock.commit_times(path, "no-such-ref")


def test_grid_in_utc_puts_the_nightly_commits_in_one_column(repo):
    _, dates = repo
    counts = commitclock.grid(dates, timedelta(0))
    assert sum(map(sum, counts)) == 4
    assert [counts[day][3] for day in range(7)] == [1, 0, 0, 0, 1, 2, 0]


def test_grid_as_recorded_keeps_each_wall_clock(repo):
    _, dates = repo
    counts = commitclock.grid(dates)
    assert counts[3][23] == 1  # Thursday 23:30 at -4
    assert counts[4][23] == 1  # Friday 23:10 at -4
    assert counts[5][3] == 1  # Saturday 03:45 UTC
    assert counts[0][9] == 1  # Monday 09:00 at +5:30
    assert sum(map(sum, counts)) == 4


def test_grid_with_another_offset():
    # 02:00 UTC on Monday is 22:00 on Sunday at -4, and 07:30 Monday at +5:30.
    t = at("2026-09-28T02:00:00+00:00")
    assert commitclock.grid([t], timedelta(hours=-4))[6][22] == 1
    assert commitclock.grid([t], timedelta(hours=5, minutes=30))[0][7] == 1


def test_parse_offset_and_its_name():
    cases = {"0": "UTC", "-4": "UTC-4", "+5:30": "UTC+5:30", "-9:30": "UTC-9:30", "8": "UTC+8"}
    for text, name in cases.items():
        assert commitclock.utc_name(commitclock.parse_offset(text)) == name
    assert commitclock.parse_offset("-9:30") == -timedelta(hours=9, minutes=30)
    with pytest.raises(ValueError):
        commitclock.parse_offset("24")
    for bad in ("east", "4:60", "1:-30", "--4", "+-4", "4:5", "", "-", "123"):
        with pytest.raises(ValueError):
            commitclock.parse_offset(bad)


# --- shading, summaries, and the text table ---------------------------------


def test_shade_runs_light_to_dark_with_empty_cells_neutral():
    assert commitclock.shade(0, 5) == commitclock.EMPTY
    assert commitclock.shade(1, 5) == commitclock.RAMP[0]
    assert commitclock.shade(5, 5) == commitclock.RAMP[-1]
    steps = [commitclock.RAMP.index(commitclock.shade(n, 9)) for n in range(1, 10)]
    assert steps == sorted(steps)
    # A grid whose fullest cell holds one commit uses a middle step, not the palest.
    assert commitclock.shade(1, 1) == commitclock.RAMP[len(commitclock.RAMP) // 2]


def test_busiest_prefers_the_largest_then_the_earliest():
    counts = [[0] * 24 for _ in range(7)]
    assert commitclock.busiest(counts) is None
    counts[4][3] = 2
    counts[1][20] = 2
    counts[6][0] = 1
    assert commitclock.busiest(counts) == (1, 20, 2)


def test_table_totals_add_up(repo):
    _, dates = repo
    lines = commitclock.table(commitclock.grid(dates, timedelta(0))).splitlines()
    assert len(lines) == 9
    assert lines[1].startswith("Mon") and lines[1].split()[-1] == "1"
    assert lines[6].startswith("Sat") and lines[6].split()[-1] == "2"
    assert lines[-1].split()[-1] == "4"
    assert lines[-1].split()[4] == "4"  # the 03:00 column


# --- the picture ------------------------------------------------------------


def test_svg_has_a_cell_for_every_hour_and_parses(repo):
    _, dates = repo
    counts = commitclock.grid(dates, timedelta(0))
    root = ET.fromstring(commitclock.render_svg(counts, "a <subtitle> & more"))
    titles = [t.text for t in root.iter(f"{SVG}title")]
    cells = [t for t in titles if t.split()[0] in commitclock.DAY_NAMES and ":00 to" in t]
    assert len(cells) == 7 * 24
    assert "Saturday 03:00 to 03:59: 2 commits" in cells
    assert "Monday 03:00 to 03:59: 1 commit" in cells
    texts = [t.text for t in root.iter(f"{SVG}text")]
    assert "a <subtitle> & more" in texts
    assert any("(4 commits)" in (t or "") for t in texts)


def test_svg_of_an_empty_grid_still_draws():
    counts = [[0] * 24 for _ in range(7)]
    root = ET.fromstring(commitclock.render_svg(counts))
    fills = {r.get("fill") for r in root.iter(f"{SVG}rect")}
    assert fills == {"#fff", commitclock.EMPTY}


# --- the command line -------------------------------------------------------


def test_main_writes_the_svg(repo, tmp_path, capsys):
    path, _ = repo
    out = tmp_path / "out" / "clock.svg"
    assert commitclock.main(["--repo", str(path), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "busiest hour: Saturday 03:00, 2 commits" in text
    svg = out.read_text()
    assert "from 2026-09-25 to 2026-09-28, in UTC" in svg
    ET.fromstring(svg)


def test_main_recorded_and_offset_options(repo, capsys):
    path, _ = repo
    assert commitclock.main(["--repo", str(path), "--recorded"]) == 0
    assert "busiest hour: Monday 09:00, 1 commit\n" in capsys.readouterr().out
    # At -4 the Saturday 03:45 UTC commit joins Friday's 23:10.
    assert commitclock.main(["--repo", str(path), "--utc-offset", "-4"]) == 0
    assert "busiest hour: Friday 23:00, 2 commits" in capsys.readouterr().out
    # A negative offset with minutes has to be passed with "=".
    assert commitclock.main(["--repo", str(path), "--utc-offset=-9:30"]) == 0
    assert "busiest hour: Thursday 18:00, 1 commit\n" in capsys.readouterr().out


def test_recorded_date_range_follows_the_wall_clocks(tmp_path, monkeypatch, repo):
    # 2 January at +14 happens before 1 January at -12, but on their own wall
    # clocks the range runs from the 1st to the 2nd, not backwards.
    path, _ = repo
    times = [at("2026-01-02T00:30:00+14:00"), at("2026-01-01T23:00:00-12:00")]
    assert times[0] < times[1]
    out = tmp_path / "clock.svg"
    monkeypatch.setattr(commitclock, "commit_times", lambda repo, ref="HEAD": times)
    assert commitclock.main(["--repo", str(path), "--recorded", "--out", str(out)]) == 0
    assert "from 2026-01-01 to 2026-01-02, in each commit" in out.read_text()


def test_main_fails_cleanly(repo, capsys):
    path, _ = repo
    assert commitclock.main(["--repo", str(path), "--ref", "nope"]) == 1
    assert commitclock.main(["--repo", str(path), "--utc-offset", "x"]) == 1
    assert "git log failed" in capsys.readouterr().err


def test_runs_on_this_repository(capsys):
    # CI's checkout is shallow, so this repository may have a single commit.
    assert commitclock.main([]) == 0
    assert "total" in capsys.readouterr().out


# --- pull requests ----------------------------------------------------------

API = """[
  {"number": 2, "user": {"login": "someone"}, "created_at": "2026-09-27T03:15:28Z",
   "merged_at": "2026-09-27T03:25:11Z", "title": "second"},
  {"number": 3, "user": {"login": "someone"}, "created_at": "2026-09-27T04:00:00Z",
   "merged_at": null, "title": "closed without merging"},
  {"number": 1, "user": {"login": "dependabot[bot]"}, "created_at": "2026-09-25T11:51:00Z",
   "merged_at": "2026-09-27T03:14:00Z", "title": "a bump"}
]"""


def test_read_prs_takes_the_api_array_and_skips_unmerged():
    prs = commitclock.read_prs(API)
    assert [pr.number for pr in prs] == [1, 2]  # oldest merge first
    bump, second = prs
    assert bump.bot and not second.bot
    assert second.author == "someone"
    assert second.opened == at("2026-09-27T03:15:28+00:00")
    assert second.minutes == pytest.approx(9 + 43 / 60)


def test_read_prs_takes_one_object_per_line_and_bare_logins():
    lines = (
        '{"number": 7, "user": "me", "created_at": "2026-10-01T03:00:00Z", '
        '"merged_at": "2026-10-01T03:08:00Z"}\n\n'
    )
    (pr,) = commitclock.read_prs(lines)
    assert (pr.number, pr.author, pr.minutes) == (7, "me", 8)
    assert commitclock.read_prs("") == []
    assert commitclock.read_prs("[]") == []


def test_duration_reads_naturally():
    assert commitclock.duration(44 / 60) == "44 s"
    assert commitclock.duration(9.6) == "10 min"
    assert commitclock.duration(65) == "1 h 05 min"
    assert commitclock.duration(15 * 60 + 21) == "15 h 21 min"
    assert commitclock.duration(39 * 60 + 23) == "1 d 15 h"


def test_pr_table_gives_medians_for_people_and_bots_apart():
    text = commitclock.pr_table(commitclock.read_prs(API), UTC)
    lines = text.splitlines()
    assert lines[0].startswith("#1    Fri 2026-09-25 11:51 -> 09-27 03:14")
    assert lines[0].endswith("(bot)")
    assert lines[1].startswith("#2    Sun 2026-09-27 03:15 ->       03:25")
    assert "1 pull requests: median 10 min, longest 10 min" in text
    assert "bots' pull requests, 1: median 1 d 15 h" in text
    # On another clock the times move and the durations don't.
    shifted = commitclock.pr_table(commitclock.read_prs(API), timezone(timedelta(hours=-4)))
    assert "Sat 2026-09-26 23:15 -> 09-26 23:25" not in shifted
    assert "#2    Sat 2026-09-26 23:15 ->       23:25      10 min" in shifted


def test_prs_svg_leaves_bots_out_and_parses():
    prs = commitclock.read_prs(API)
    root = ET.fromstring(commitclock.render_prs_svg(prs, UTC, "sub & <title>"))
    titles = [t.text for t in root.iter(f"{SVG}title")]
    assert "#2: opened 2026-09-27 03:15, merged 03:25, 10 min" in titles
    assert not any(t.startswith("#1:") for t in titles)
    assert "median: 10 min" in titles
    texts = [t.text for t in root.iter(f"{SVG}text")]
    assert "sub & <title>" in texts
    assert any("(1 pull requests)" in (t or "") for t in texts)
    # With nothing to draw it still draws.
    ET.fromstring(commitclock.render_prs_svg([], UTC))


def test_main_with_prs(repo, tmp_path, capsys):
    path, _ = repo
    data = tmp_path / "prs.json"
    data.write_text(API)
    out = tmp_path / "out" / "prs.svg"
    argv = ["--repo", str(path), "--prs", str(data), "--prs-out", str(out)]
    assert commitclock.main(argv) == 0
    assert "median 10 min" in capsys.readouterr().out
    assert "1 from bots left out" in out.read_text()
    # --recorded has no single zone, so the pull requests' times are in UTC.
    assert commitclock.main([*argv, "--recorded"]) == 0
    assert "times in UTC" in out.read_text()
    assert commitclock.main([*argv, "--utc-offset=-4"]) == 0
    assert "times in UTC-4" in out.read_text()


def test_main_with_prs_fails_cleanly(repo, tmp_path, capsys):
    path, _ = repo
    assert commitclock.main(["--repo", str(path), "--prs", str(tmp_path / "none")]) == 1
    bad = tmp_path / "bad.json"
    bad.write_text('[{"number": 1, "merged_at": "2026-01-01T00:00:00Z"}]')
    assert commitclock.main(["--repo", str(path), "--prs", str(bad)]) == 1
    bad.write_text("{not json")
    assert commitclock.main(["--repo", str(path), "--prs", str(bad)]) == 1
    with pytest.raises(SystemExit):
        commitclock.main(["--repo", str(path), "--prs-out", str(tmp_path / "x.svg")])


def test_committed_snapshot_reads():
    snapshot = commitclock.Path(commitclock.__file__).parent / "out" / "prs.jsonl"
    prs = commitclock.read_prs(snapshot.read_text())
    assert len(prs) >= 38
    assert all(pr.merged >= pr.opened for pr in prs)
