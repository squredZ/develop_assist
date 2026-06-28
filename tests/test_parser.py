# tests/test_parser.py
from __future__ import annotations

from hilog_agent.hilog.parser import (
    HilogEvent,
    parse_hilog_file,
    parse_hilog_lines,
)


class TestHilogParser:
    def test_parse_valid_line(self):
        line = "2026-06-28 14:35:00.000 CameraService INFO Start capture"
        event = HilogEvent.parse_line(line)
        assert event is not None
        assert event.tag == "CameraService"
        assert event.level == "INFO"
        assert event.message == "Start capture"

    def test_parse_invalid_line_returns_none(self):
        event = HilogEvent.parse_line("not a valid hilog line")
        assert event is None

    def test_timestamp_includes_year(self):
        line = "2026-06-28 14:35:00.000 CameraService INFO msg"
        event = HilogEvent.parse_line(line)
        assert event is not None
        assert event.timestamp.year == 2026

    def test_parse_file_counts_unparsed(self, fixtures_dir):
        path = fixtures_dir / "logs" / "sample.hilog"
        result = parse_hilog_file(path)
        assert result.total_lines == 7
        assert result.parsed == 5
        assert result.unparsed == 2

    def test_parse_lines(self, sample_hilog_lines):
        events, unparsed = parse_hilog_lines(sample_hilog_lines)
        assert len(events) == 5
        assert len(unparsed) == 0
