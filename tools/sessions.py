"""Read the sessions out of the journal: each one's heading and start time.

Every session's part of a day's entry begins with a heading of the form
``## The Nth working session: what it was about`` and, as the first line under
it, ``Started at HH:MM UTC.`` (``at about`` is fine too). The entry's file is
named for the UTC date the session started, so that date and time together
are the start. The rule starts with
the entry for 2026-10-10; earlier sessions used other headings and recorded no
start. ``python tools/sessions.py`` lists the sessions and names any entry that
breaks the rule.

Usage:
    python tools/sessions.py [--root PATH]
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULE_FROM = date(2026, 10, 10)

HEADING = re.compile(r"^## (The \S+ working session\b.*)$")
START = re.compile(r"^Started at (?:about )?(\d{1,2}):(\d{2}) UTC\b")


@dataclass(frozen=True)
class Session:
    day: date
    heading: str
    started: datetime | None


def sessions(day: date, text: str) -> list[Session]:
    """The sessions in one day's entry, in order, with their start times if given."""
    found = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        match = HEADING.match(line)
        if not match:
            continue
        rest = (s for s in lines[i + 1 :] if s.strip())
        first = next(rest, "")
        start = START.match(first)
        started = None
        if start:
            hour, minute = int(start[1]), int(start[2])
            if hour < 24 and minute < 60:
                started = datetime.combine(day, time(hour, minute), UTC)
        found.append(Session(day, match[1], started))
    return found


def entry_day(path: Path) -> date | None:
    try:
        return date.fromisoformat(path.stem)
    except ValueError:
        return None


def problems(root: Path) -> list[str]:
    """Entries from RULE_FROM on that lack a session heading or a start time."""
    out = []
    for path in sorted((root / "journal").glob("*.md")):
        day = entry_day(path)
        if day is None or day < RULE_FROM:
            continue
        found = sessions(day, path.read_text(encoding="utf-8"))
        if not found:
            out.append(f"{path.name}: no '## The Nth working session' heading")
        for s in found:
            if s.started is None:
                out.append(f"{path.name}: '{s.heading}' has no 'Started at HH:MM UTC.' line")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    for path in sorted((args.root / "journal").glob("*.md")):
        day = entry_day(path)
        if day is None:
            continue
        for s in sessions(day, path.read_text(encoding="utf-8")):
            when = s.started.strftime("%H:%M") if s.started else "--:--"
            print(f"{day}  {when}  {s.heading}")
    found = problems(args.root)
    for line in found:
        print(f"rule: {line}")
    return 1 if found else 0


if __name__ == "__main__":
    raise SystemExit(main())
