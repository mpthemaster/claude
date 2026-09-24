"""Print a quick orientation for a fresh session: recent journal, backlog, projects.

Usage:
    python tools/status.py [--root PATH]
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=False
        ).stdout.strip()
    except OSError:
        return ""


def journal_entries(root: Path, limit: int = 3) -> list[Path]:
    entries = sorted((root / "journal").glob("*.md"))
    return entries[-limit:]


def backlog_section(root: Path, heading: str = "Now") -> str:
    path = root / "BACKLOG.md"
    if not path.exists():
        return ""
    text = path.read_text()
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return match.group(1).strip() if match else ""


def projects(root: Path) -> list[tuple[str, str]]:
    found = []
    for readme in sorted((root / "projects").glob("*/README.md")):
        first = next((line for line in readme.read_text().splitlines() if line.strip()), "")
        found.append((readme.parent.name, first.lstrip("# ").strip()))
    return found


def render(root: Path) -> str:
    out = []
    branch = git(root, "rev-parse", "--abbrev-ref", "HEAD")
    last = git(root, "log", "-1", "--format=%h %ad %s", "--date=short")
    out.append(f"repo:    {root}")
    out.append(f"branch:  {branch or '?'}")
    out.append(f"last:    {last or '(no commits)'}")
    out.append("")
    out.append("projects:")
    for slug, title in projects(root) or [("(none)", "")]:
        out.append(f"  - {slug}: {title}")
    out.append("")
    out.append("backlog / Now:")
    now = backlog_section(root)
    out.extend(f"  {line}" for line in (now.splitlines() or ["(empty)"]))
    out.append("")
    out.append("recent journal:")
    for entry in journal_entries(root) or []:
        lines = [line for line in entry.read_text().splitlines() if line.strip()]
        title = lines[0].lstrip("# ").strip() if lines else ""
        out.append(f"  - {entry.name}: {title}")
    if not journal_entries(root):
        out.append("  (no entries yet)")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print repo orientation.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    print(render(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
