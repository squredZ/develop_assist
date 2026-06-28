# tests/test_matcher.py
from __future__ import annotations

import re
from datetime import datetime, timedelta

import pytest
from hilog_agent.hilog.parser import HilogEvent
from hilog_agent.hilog.matcher import (
    filter_by_time_window,
    match_logs,
    MatchResult,
)


def make_event(ts: str, tag: str = "T", level: str = "INFO", msg: str = "msg"):
    return HilogEvent(
        timestamp=datetime.strptime(ts, "%Y-%m-%d %H:%M:%S.%f"),
        tag=tag,
        level=level,
        message=msg,
        raw=f"{ts} {tag} {level} {msg}",
    )


class TestTimeWindow:
    def test_events_within_window(self):
        center = datetime(2026, 6, 28, 14, 35, 0)
        events = [
            make_event("2026-06-28 14:34:50.000"),  # 10s before
            make_event("2026-06-28 14:35:00.000"),  # exact
            make_event("2026-06-28 14:35:10.000"),  # 10s after
            make_event("2026-06-28 14:33:00.000"),  # 120s before — out
        ]
        filtered = filter_by_time_window(
            events, center, before_seconds=60, after_seconds=60
        )
        assert len(filtered) == 3

    def test_asymmetric_window(self):
        center = datetime(2026, 6, 28, 14, 35, 0)
        events = [
            make_event("2026-06-28 14:33:50.000"),  # 70s before
            make_event("2026-06-28 14:35:05.000"),  # 5s after — in
        ]
        filtered = filter_by_time_window(
            events, center, before_seconds=120, after_seconds=30
        )
        assert len(filtered) == 2  # both in asymmetric window


class TestMatchLogs:
    def test_substring_match(self):
        events = [make_event("2026-06-28 14:35:00.000", "X", "INFO", "hello world")]
        hits = match_logs(events, tag="X", pattern="hello", match_type="substring")
        assert len(hits) == 1
        assert hits[0].event.message == "hello world"

    def test_regex_match(self):
        events = [make_event("2026-06-28 14:35:00.000", "X", "INFO", "error 42")]
        hits = match_logs(events, tag="X", pattern=r"error \d+", match_type="regex")
        assert len(hits) == 1

    def test_level_filter(self):
        events = [
            make_event("2026-06-28 14:35:00.000", "X", "INFO", "msg"),
            make_event("2026-06-28 14:35:01.000", "X", "ERROR", "msg"),
        ]
        hits = match_logs(events, tag="X", pattern="msg", match_type="substring", level="ERROR")
        assert len(hits) == 1
        assert hits[0].event.level == "ERROR"

    def test_no_match_returns_empty(self):
        events = [make_event("2026-06-28 14:35:00.000", "X", "INFO", "hello")]
        hits = match_logs(events, tag="X", pattern="world", match_type="substring")
        assert len(hits) == 0
