"""The CI configuration: a hang has to be a quick red run.

Every workflow job has a time limit, and the pytest configuration in
pyproject.toml makes a test that hangs dump its traceback and stop the run,
so the log says where it hung instead of the job sitting at GitHub's
six-hour default.
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
PYPROJECT = ROOT / "pyproject.toml"

JOB = re.compile(r"  ([A-Za-z0-9_-]+):")
TIME_LIMIT = re.compile(r"    timeout-minutes: (\d+)")


def jobs(text: str) -> dict[str, list[str]]:
    """Each job's name and its body, from a workflow indented by two spaces.

    Not a YAML parser. A job is a line indented by exactly two spaces under
    `jobs:` that names a mapping, and its body runs to the next such line or
    to the next top-level key. The workflows here are short and hand-written
    in that shape, and the tests fail loudly (no jobs found) if it changes.
    """
    found: dict[str, list[str]] = {}
    current: str | None = None
    in_jobs = False
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line == "jobs:":
            in_jobs = True
            continue
        if not line.startswith(" "):
            in_jobs = False
            current = None
            continue
        if not in_jobs:
            continue
        if match := JOB.fullmatch(line):
            current = match.group(1)
            found[current] = []
        elif current is not None:
            found[current].append(line)
    return found


def time_limits(body: list[str]) -> list[int]:
    return [int(m.group(1)) for line in body if (m := TIME_LIMIT.fullmatch(line))]


def test_jobs_reads_the_shape_the_workflows_use():
    text = (
        "name: x\n\non:\n  push:\n\njobs:\n"
        "  # a comment\n"
        "  first:\n    runs-on: ubuntu-latest\n    timeout-minutes: 7\n"
        "    steps:\n      - run: echo hi\n"
        "  second:\n    needs: first\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: echo timeout-minutes: 99\n"
        "\nother:\n  third:\n    timeout-minutes: 3\n"
    )
    found = jobs(text)
    assert list(found) == ["first", "second"]
    assert time_limits(found["first"]) == [7]
    assert time_limits(found["second"]) == []


def test_every_workflow_has_jobs():
    assert WORKFLOWS, "no workflows under .github/workflows"
    for workflow in WORKFLOWS:
        assert jobs(workflow.read_text()), f"{workflow.name}: no jobs found; layout changed?"


def test_every_workflow_job_has_a_time_limit_well_under_an_hour():
    for workflow in WORKFLOWS:
        for name, body in jobs(workflow.read_text()).items():
            limits = time_limits(body)
            assert len(limits) == 1, f"{workflow.name}: job {name!r} needs one timeout-minutes"
            assert 1 <= limits[0] <= 30, f"{workflow.name}: job {name!r} allows {limits[0]} min"


def pytest_options() -> dict:
    with PYPROJECT.open("rb") as f:
        return tomllib.load(f)["tool"]["pytest"]["ini_options"]


def test_a_hung_test_is_stopped_before_the_job_is():
    options = pytest_options()
    per_test = float(options["faulthandler_timeout"])
    assert options["faulthandler_exit_on_timeout"] is True
    # Far above the slowest real test (about two seconds), and the traceback
    # has to be printed before the job's own limit cuts the log off.
    assert per_test >= 10
    ci = jobs((ROOT / ".github" / "workflows" / "ci.yml").read_text())
    (job_minutes,) = time_limits(ci["check"])
    assert per_test < job_minutes * 60 / 2


def test_a_hung_test_stops_the_run_with_its_traceback(tmp_path):
    # The repository's own pytest configuration, with only the duration
    # shortened so the test doesn't take a minute. Without
    # faulthandler_exit_on_timeout the traceback is printed and the run
    # keeps hanging, which the subprocess timeout below turns into a failure.
    test = tmp_path / "test_hang.py"
    test.write_text(
        "import time\n\n\ndef test_hangs():\n    while True:\n        time.sleep(0.05)\n"
    )
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-c",
        str(PYPROJECT),
        "--rootdir",
        str(tmp_path),
        "-p",
        "no:cacheprovider",
        "-o",
        "faulthandler_timeout=1",
        str(test),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        raise AssertionError("pytest kept running after the hung test") from None
    assert result.returncode != 0
    assert "Timeout" in result.stderr, result.stderr
    assert "test_hangs" in result.stderr, result.stderr
