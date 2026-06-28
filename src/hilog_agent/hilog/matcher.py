"""Time-window filtering and log pattern matching."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal

from hilog_agent.hilog.parser import HilogEvent


def filter_by_time_window(
    events: list[HilogEvent],
    center: datetime,
    before_seconds: int,
    after_seconds: int,
) -> list[HilogEvent]:
    """Return events within [center - before_seconds, center + after_seconds]."""
    start = center - timedelta(seconds=before_seconds)
    end = center + timedelta(seconds=after_seconds)
    return [e for e in events if start <= e.timestamp <= end]


@dataclass(frozen=True, slots=True)
class MatchResult:
    event: HilogEvent
    match_text: str


def match_logs(
    events: list[HilogEvent],
    tag: str,
    pattern: str,
    match_type: Literal["substring", "regex"],
    level: str | None = None,
) -> list[MatchResult]:
    """Match events by tag + pattern. Optional level filter."""
    results: list[MatchResult] = []

    if match_type == "regex":
        compiled = re.compile(pattern)
    else:
        compiled = None

    for evt in events:
        if evt.tag != tag:
            continue
        if level is not None and evt.level != level:
            continue

        if match_type == "substring":
            if pattern in evt.message:
                results.append(MatchResult(event=evt, match_text=evt.message))
        elif match_type == "regex" and compiled is not None:
            m = compiled.search(evt.message)
            if m:
                results.append(MatchResult(event=evt, match_text=m.group()))

    return results
