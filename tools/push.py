"""Push the current branch to origin, and nothing else.

Only claude/* branches are pushed: never force, never a deletion, never a
different destination ref, never tags, and no arguments are accepted. This is
the only push command the close-out procedure uses, and it lives under
tools/ so the session settings that already permit running tools cover it.

Usage:
    python3 tools/push.py
"""

from __future__ import annotations

import re
import subprocess
import sys

BRANCH = re.compile(r"^refs/heads/claude/[A-Za-z0-9._-]+$")


def current_ref() -> str:
    """The full symbolic ref of HEAD, or an empty string when detached.

    The full ref is used so a tag with the branch's name can't confuse the
    check, and the push uses it fully qualified so the destination is always
    a branch.
    """
    result = subprocess.run(
        ["git", "symbolic-ref", "-q", "HEAD"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if args:
        print("push.py: takes no arguments", file=sys.stderr)
        return 1
    ref = current_ref()
    if not BRANCH.match(ref):
        shown = ref or "detached HEAD"
        print(
            f"push.py: refusing to push '{shown}'; only claude/* branches are pushed from here",
            file=sys.stderr,
        )
        return 1
    cmd = ["git", "push", "--no-follow-tags", "-u", "origin", f"{ref}:{ref}"]
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
