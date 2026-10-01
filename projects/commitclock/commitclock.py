"""When commits land in this repo, hour by weekday.

Reads the committer dates of every commit reachable from a ref, counts them
in a 7 x 24 grid (Monday to Sunday, midnight to 11pm), and prints the grid
or draws it as an SVG heatmap with the hour and weekday totals along its
edges.

Every commit goes on one clock, UTC unless --utc-offset names another;
--recorded keeps each commit's wall-clock time in whatever zone it was
recorded in, which mixes clocks when committers sit in different zones.

    python projects/commitclock/commitclock.py
    python projects/commitclock/commitclock.py --out projects/commitclock/out/clock.svg
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# One blue, light to dark, for counts; an empty cell is a pale neutral.
RAMP = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")
EMPTY = "#f2f2f0"
INK, MUTED, GRID = "#111", "#555", "#e5e5e5"


def commit_times(repo: Path, ref: str = "HEAD") -> list[datetime]:
    """The committer date of every commit reachable from `ref`, newest first.

    Each comes back timezone-aware, in the offset it was recorded with. A
    shallow clone yields only the commits it has.
    """
    result = subprocess.run(
        ["git", "log", "--format=%cI", ref],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git log failed in {repo}: {result.stderr.strip()}")
    return [datetime.fromisoformat(line) for line in result.stdout.split()]


def grid(times: Iterable[datetime], offset: timedelta | None = None) -> list[list[int]]:
    """Counts by weekday (row 0 is Monday) and hour (column 0 is midnight).

    With `offset`, every time is first moved to that UTC offset; without it,
    each keeps the wall-clock time it was recorded with.
    """
    zone = None if offset is None else timezone(offset)
    counts = [[0] * 24 for _ in range(7)]
    for t in times:
        if zone is not None:
            t = t.astimezone(zone)
        counts[t.weekday()][t.hour] += 1
    return counts


def shade(count: int, peak: int) -> str:
    """The fill for a cell: EMPTY for zero, else a ramp step growing with count."""
    if count == 0:
        return EMPTY
    if peak <= 1:
        return RAMP[len(RAMP) // 2]
    # 1 maps to the lightest step and `peak` to the darkest.
    step = round((count - 1) * (len(RAMP) - 1) / (peak - 1))
    return RAMP[step]


def busiest(counts: list[list[int]]) -> tuple[int, int, int] | None:
    """The (weekday, hour, count) of the fullest cell, earliest first on ties."""
    best = None
    for day, row in enumerate(counts):
        for hour, n in enumerate(row):
            if n and (best is None or n > best[2]):
                best = (day, hour, n)
    return best


def plural(n: int) -> str:
    return f"{n} commit" + ("" if n == 1 else "s")


def hour_label(hour: int) -> str:
    return f"{hour:02d}:00"


def table(counts: list[list[int]]) -> str:
    """The grid as text: one row per weekday, '.' for an empty hour."""
    header = "     " + "".join(f"{h:>3}" for h in range(24)) + "  total"
    lines = [header]
    for day, row in enumerate(counts):
        cells = "".join(f"{n if n else '.':>3}" for n in row)
        lines.append(f"{DAYS[day]:<5}{cells}  {sum(row):>5}")
    hours = "".join(f"{sum(col):>3}" for col in zip(*counts, strict=True))
    lines.append(f"{'all':<5}{hours}  {sum(map(sum, counts)):>5}")
    return "\n".join(lines)


def render_svg(counts: list[list[int]], subtitle: str = "") -> str:
    """The grid as an SVG heatmap, with hour totals above and weekday totals right."""
    cell, gap = 24, 2
    left, top = 48, 96
    bar_h, bar_w = 40, 64
    width = left + 24 * cell + 16 + bar_w + 40
    height = top + 7 * cell + 56
    peak = max(max(row) for row in counts)
    total = sum(map(sum, counts))
    hour_totals = [sum(col) for col in zip(*counts, strict=True)]
    day_totals = [sum(row) for row in counts]
    hour_peak = max(hour_totals) or 1
    day_peak = max(day_totals) or 1

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'font-family="system-ui, sans-serif" font-size="12">',
        f'<rect width="{width}" height="{height}" fill="#fff"/>',
        f'<text x="{left}" y="20" font-size="14" font-weight="600">'
        f"When commits land, by weekday and hour ({total} commits)</text>",
    ]
    if subtitle:
        parts.append(f'<text x="{left}" y="38" fill="{MUTED}">{escape(subtitle)}</text>')

    # Hour totals: a thin bar over each column.
    base = top - 8
    for hour, n in enumerate(hour_totals):
        if not n:
            continue
        x = left + hour * cell + gap / 2
        h = max(2.0, bar_h * n / hour_peak)
        parts.append(
            f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{cell - gap}" height="{h:.1f}" '
            f'rx="2" fill="{RAMP[3]}"><title>{hour_label(hour)} to {hour:02d}:59: '
            f"{plural(n)}</title></rect>"
        )
    parts.append(
        f'<line x1="{left}" y1="{base}" x2="{left + 24 * cell}" y2="{base}" stroke="{GRID}"/>'
    )

    # The grid itself.
    for day, row in enumerate(counts):
        y = top + day * cell
        parts.append(
            f'<text x="{left - 8}" y="{y + cell / 2 + 4:.1f}" text-anchor="end" '
            f'fill="{MUTED}">{DAYS[day]}</text>'
        )
        for hour, n in enumerate(row):
            x = left + hour * cell
            fill = shade(n, peak)
            parts.append(
                f'<rect x="{x + gap / 2:.1f}" y="{y + gap / 2:.1f}" width="{cell - gap}" '
                f'height="{cell - gap}" rx="3" fill="{fill}"><title>{DAY_NAMES[day]} '
                f"{hour_label(hour)} to {hour:02d}:59: {plural(n)}"
                "</title></rect>"
            )
            if n:
                dark = RAMP.index(fill) >= 3
                parts.append(
                    f'<text x="{x + cell / 2:.1f}" y="{y + cell / 2 + 4:.1f}" '
                    f'text-anchor="middle" font-size="11" fill="{"#fff" if dark else INK}" '
                    f'pointer-events="none">{n}</text>'
                )

    # Weekday totals: a thin bar right of each row, with its number.
    bx = left + 24 * cell + 16
    for day, n in enumerate(day_totals):
        y = top + day * cell + gap / 2
        if n:
            w = max(2.0, bar_w * n / day_peak)
            parts.append(
                f'<rect x="{bx}" y="{y:.1f}" width="{w:.1f}" height="{cell - gap}" rx="2" '
                f'fill="{RAMP[3]}"><title>{DAY_NAMES[day]}: {plural(n)}</title></rect>'
            )
        parts.append(
            f'<text x="{bx + (max(2.0, bar_w * n / day_peak) if n else 0) + 4:.1f}" '
            f'y="{y + cell / 2 + 3:.1f}" fill="{MUTED}">{n}</text>'
        )

    # Hour labels every three hours, under the grid.
    axis_y = top + 7 * cell + 16
    for hour in range(0, 24, 3):
        x = left + hour * cell + cell / 2
        parts.append(
            f'<text x="{x:.1f}" y="{axis_y}" text-anchor="middle" fill="{MUTED}">'
            f"{hour_label(hour)}</text>"
        )
    parts.append(
        f'<text x="{left + 12 * cell}" y="{axis_y + 24}" text-anchor="middle" fill="{MUTED}">'
        "hour of the day; bars above are hour totals, bars right are weekday totals</text>"
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


OFFSET = re.compile(r"([+-]?)(\d{1,2})(?::(\d{2}))?")


def parse_offset(text: str) -> timedelta:
    """'-4', '+5:30' or '0' as a UTC offset; anything malformed is a ValueError."""
    match = OFFSET.fullmatch(text)
    if not match:
        raise ValueError(f"not a UTC offset: {text}")
    sign, hours, minutes = match.groups()
    if int(hours) > 23 or int(minutes or 0) > 59:
        raise ValueError(f"offset out of range: {text}")
    offset = timedelta(hours=int(hours), minutes=int(minutes or 0))
    return -offset if sign == "-" else offset


def utc_name(offset: timedelta) -> str:
    """'UTC', 'UTC-4' or 'UTC+5:30'."""
    if not offset:
        return "UTC"
    sign = "-" if offset < timedelta(0) else "+"
    minutes = abs(offset) // timedelta(minutes=1)
    hours, minutes = divmod(minutes, 60)
    return f"UTC{sign}{hours}" + (f":{minutes:02d}" if minutes else "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--ref", default="HEAD")
    clock = parser.add_mutually_exclusive_group()
    clock.add_argument(
        "--utc-offset",
        default="0",
        help="put every commit in this UTC offset, e.g. +5:30, or =-4 for a negative "
        "one (default: 0)",
    )
    clock.add_argument(
        "--recorded",
        action="store_true",
        help="keep each commit's own recorded zone instead",
    )
    parser.add_argument("--out", type=Path, help="write the SVG heatmap here")
    args = parser.parse_args(argv)

    try:
        offset = None if args.recorded else parse_offset(args.utc_offset)
        times = commit_times(args.repo, args.ref)
    except (RuntimeError, ValueError) as err:
        print(err, file=sys.stderr)
        return 1

    counts = grid(times, offset)
    print(table(counts))
    top = busiest(counts)
    if top:
        day, hour, n = top
        print(f"\nbusiest hour: {DAY_NAMES[day]} {hour_label(hour)}, {plural(n)}")

    if args.out:
        if times:
            # The dates on the clock the grid uses: in --recorded mode each
            # commit's own, which need not follow the order of the instants.
            days = [(t if offset is None else t.astimezone(timezone(offset))).date() for t in times]
            newest, oldest = max(days), min(days)
            zone = "each commit's own time zone" if offset is None else utc_name(offset)
            subtitle = (
                f"Commits{'' if args.ref == 'HEAD' else ' on ' + args.ref} "
                f"from {oldest:%Y-%m-%d} to {newest:%Y-%m-%d}, "
                f"in {zone}. Darker is more."
            )
        else:
            subtitle = "No commits."
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render_svg(counts, subtitle))
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
