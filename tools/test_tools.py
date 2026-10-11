import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path

import new_project
import sessions
import status

ROOT = Path(__file__).resolve().parent.parent


def test_new_project_scaffolds_files(tmp_path):
    target = new_project.create(tmp_path, "hello-world", "Says hello.")
    assert (target / "README.md").exists()
    assert (target / "hello_world.py").exists()
    assert (target / "test_hello_world.py").exists()
    assert "Says hello." in (target / "README.md").read_text()


def test_new_project_scaffold_passes_its_own_test(tmp_path):
    target = new_project.create(tmp_path, "demo", "A demo.")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(target)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_new_project_rejects_bad_slug(tmp_path):
    try:
        new_project.create(tmp_path, "Bad Slug", "x")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_new_project_refuses_to_overwrite(tmp_path):
    new_project.create(tmp_path, "twice", "x")
    try:
        new_project.create(tmp_path, "twice", "x")
    except FileExistsError:
        return
    raise AssertionError("expected FileExistsError")


def test_status_renders_real_repo():
    text = status.render(ROOT)
    assert "projects:" in text
    assert "truchet" in text
    assert "backlog / Now:" in text


def test_backlog_section_extracts_heading(tmp_path):
    (tmp_path / "BACKLOG.md").write_text("# B\n\n## Now\n\n- a\n- b\n\n## Soon\n\n- c\n")
    assert status.backlog_section(tmp_path, "Now") == "- a\n- b"
    assert status.backlog_section(tmp_path, "Soon") == "- c"
    assert status.backlog_section(tmp_path, "Missing") == ""


def test_status_handles_empty_root(tmp_path):
    text = status.render(tmp_path)
    assert "(none)" in text
    assert "(no entries yet)" in text


def test_journal_sessions_reads_headings_and_start_times():
    text = (
        "# 2026-10-11: a day\n\n"
        "## The first working session: one\n\n"
        "Started at 03:12 UTC. Then more.\n\n"
        "## What I did\n\nThings.\n\n"
        "## The second working session: two\n\n"
        "Started at about 9:05 UTC.\n\n"
        "## The third working session\n\nNo time here.\n"
    )
    day = date(2026, 10, 11)
    found = sessions.sessions(day, text)
    assert [s.heading for s in found] == [
        "The first working session: one",
        "The second working session: two",
        "The third working session",
    ]
    assert found[0].started == datetime(2026, 10, 11, 3, 12, tzinfo=UTC)
    assert found[1].started == datetime(2026, 10, 11, 9, 5, tzinfo=UTC)
    assert found[2].started is None


def test_journal_start_must_be_the_first_line_and_a_real_time():
    day = date(2026, 10, 11)
    late = "## The first working session\n\nSomething.\n\nStarted at 03:12 UTC.\n"
    assert sessions.sessions(day, late)[0].started is None
    bad = "## The first working session\n\nStarted at 25:70 UTC.\n"
    assert sessions.sessions(day, bad)[0].started is None


def test_journal_problems_apply_from_the_rule_date_on(tmp_path):
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "2026-10-01.md").write_text("# old\n\n## Evening\n\nNo rule yet.\n")
    (tmp_path / "journal" / "2026-10-20.md").write_text(
        "# d\n\n## The first working session\n\nStarted at 03:00 UTC.\n\n"
        "## The second working session\n\nForgot.\n"
    )
    (tmp_path / "journal" / "2026-10-21.md").write_text("# d\n\n## Night\n\nNo heading.\n")
    assert sessions.problems(tmp_path) == [
        "2026-10-20.md: 'The second working session' has no 'Started at HH:MM UTC.' line",
        "2026-10-21.md: no '## The Nth working session' heading",
    ]
    assert sessions.main(["--root", str(tmp_path)]) == 1


def test_journal_in_this_repository_keeps_the_rule():
    assert sessions.problems(ROOT) == []


def test_sessions_flags_a_start_line_under_a_mistyped_heading(tmp_path):
    (tmp_path / "journal").mkdir()
    (tmp_path / "journal" / "2026-10-20.md").write_text(
        "# d\n\n## The first working session\n\nStarted at 03:00 UTC.\n\n"
        "## Second working session: typo\n\nStarted at 05:00 UTC.\n"
    )
    assert sessions.problems(tmp_path) == [
        "2026-10-20.md: 'Started at 05:00 UTC.' is not under a '## The Nth working session' heading"
    ]
