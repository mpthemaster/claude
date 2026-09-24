import subprocess
import sys
from pathlib import Path

import new_project
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
