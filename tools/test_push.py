import subprocess
from pathlib import Path

import pytest

PUSH = Path(__file__).resolve().parent / "push.sh"


def git(*args, cwd):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def run_push(cwd, *args):
    return subprocess.run(["bash", str(PUSH), *args], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path):
    origin = tmp_path / "origin.git"
    git("init", "-q", "--bare", str(origin), cwd=tmp_path)
    work = tmp_path / "work"
    git("clone", "-q", str(origin), str(work), cwd=tmp_path)
    git("config", "user.email", "t@example.com", cwd=work)
    git("config", "user.name", "t", cwd=work)
    (work / "f").write_text("x\n")
    git("add", "f", cwd=work)
    git("commit", "-q", "-m", "init", cwd=work)
    git("push", "-q", "-u", "origin", "HEAD:main", cwd=work)
    return work


def test_pushes_a_claude_branch(repo):
    git("checkout", "-q", "-b", "claude/test-branch", cwd=repo)
    (repo / "g").write_text("y\n")
    git("add", "g", cwd=repo)
    git("commit", "-q", "-m", "more", cwd=repo)
    result = run_push(repo)
    assert result.returncode == 0, result.stderr
    heads = git("ls-remote", "--heads", "origin", cwd=repo).stdout
    assert "refs/heads/claude/test-branch" in heads


def test_refuses_branches_outside_claude(repo):
    result = run_push(repo)
    assert result.returncode == 1
    assert "refusing" in result.stderr


def test_refuses_any_arguments(repo):
    git("checkout", "-q", "-b", "claude/with-args", cwd=repo)
    for args in (["--force"], ["origin", "HEAD:main"], ["--delete", "main"]):
        result = run_push(repo, *args)
        assert result.returncode == 1, args
        assert "no arguments" in result.stderr


def test_tag_with_the_branch_name_does_not_block_the_push(repo):
    git("checkout", "-q", "-b", "claude/same", cwd=repo)
    git("tag", "claude/same", cwd=repo)
    (repo / "h").write_text("z\n")
    git("add", "h", cwd=repo)
    git("commit", "-q", "-m", "h", cwd=repo)
    result = run_push(repo)
    assert result.returncode == 0, result.stderr
    heads = git("ls-remote", "--heads", "origin", cwd=repo).stdout
    assert "refs/heads/claude/same" in heads


def test_destination_is_always_a_branch(repo):
    # An odd ref on the origin with the same short name must not become the
    # destination; the push goes to refs/heads and leaves the odd ref alone.
    origin = repo.parent / "origin.git"
    main_sha = git("rev-parse", "HEAD", cwd=repo).stdout.strip()
    git("update-ref", "refs/claude/odd", main_sha, cwd=origin)
    git("checkout", "-q", "-b", "claude/odd", cwd=repo)
    (repo / "i").write_text("w\n")
    git("add", "i", cwd=repo)
    git("commit", "-q", "-m", "i", cwd=repo)
    result = run_push(repo)
    assert result.returncode == 0, result.stderr
    refs = git("ls-remote", "origin", cwd=repo).stdout
    assert "refs/heads/claude/odd" in refs
    assert f"{main_sha}\trefs/claude/odd" in refs


def test_refuses_detached_head(repo):
    git("checkout", "-q", "--detach", cwd=repo)
    result = run_push(repo)
    assert result.returncode == 1
    assert "refusing" in result.stderr
