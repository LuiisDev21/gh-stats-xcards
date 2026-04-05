"""Contribution streak calculation for streak stat cards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

_MONTH_ABBR = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def format_long_date(d: date) -> str:
    """English short month, e.g. ``Aug 10, 2016``."""

    return f"{_MONTH_ABBR[d.month - 1]} {d.day}, {d.year}"


def format_streak_range(start: date, end: date) -> str:
    """Range like ``Mar 21 - Apr 5, 2026`` or cross-year long form."""

    if start > end:
        return "—"
    if start.year == end.year:
        return (
            f"{_MONTH_ABBR[start.month - 1]} {start.day} - "
            f"{_MONTH_ABBR[end.month - 1]} {end.day}, {end.year}"
        )
    return f"{format_long_date(start)} - {format_long_date(end)}"


@dataclass(frozen=True)
class StreakMetrics:
    """Current and longest contribution streaks."""

    current_streak: int
    current_start: date | None
    current_end: date | None
    longest_streak: int
    longest_start: date | None
    longest_end: date | None


def compute_streak_metrics(
    counts_by_day: dict[str, int],
    *,
    account_start: date,
    today: date,
) -> StreakMetrics:
    """Compute streaks from a merged GitHub calendar (UTC dates, ISO keys).

    A day counts as active when ``contributionCount > 0`` for that date.
    Current streak walks backward from ``today``, skipping trailing inactive days,
    then counts consecutive active days.
    """

    def day_count(d: date) -> int:
        return int(counts_by_day.get(d.isoformat(), 0))

    d = today
    while d >= account_start and day_count(d) == 0:
        d -= timedelta(days=1)

    if d < account_start:
        current_streak = 0
        current_start = None
        current_end = None
    else:
        current_end = d
        streak = 0
        while d >= account_start and day_count(d) > 0:
            streak += 1
            d -= timedelta(days=1)
        current_start = d + timedelta(days=1)
        current_streak = streak

    longest = 0
    longest_start: date | None = None
    longest_end: date | None = None
    run = 0
    run_start: date | None = None
    walker = account_start
    while walker <= today:
        if day_count(walker) > 0:
            if run == 0:
                run_start = walker
            run += 1
            if run > longest and run_start is not None:
                longest = run
                longest_start = run_start
                longest_end = walker
        else:
            run = 0
            run_start = None
        walker += timedelta(days=1)

    return StreakMetrics(
        current_streak=current_streak,
        current_start=current_start,
        current_end=current_end,
        longest_streak=longest,
        longest_start=longest_start,
        longest_end=longest_end,
    )
