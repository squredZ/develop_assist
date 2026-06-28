"""Hilog line parser — extract timestamp, tag, level, message."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

HILOG_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(\S+?)\s+"  # tag (non-whitespace)
    r"([A-Z]+)\s+"  # level (uppercase)
    r"(.*)"  # message
)

HILOG_DT_FMT = "%Y-%m-%d %H:%M:%S.%f"


@dataclass(frozen=True, slots=True)
class HilogEvent:
    timestamp: datetime
    tag: str
    level: str
    message: str
    raw: str

    @classmethod
    def parse_line(cls, line: str) -> HilogEvent | None:
        m = HILOG_RE.match(line.strip())
        if not m:
            return None
        return cls(
            timestamp=datetime.strptime(m.group(1), HILOG_DT_FMT),
            tag=m.group(2),
            level=m.group(3),
            message=m.group(4),
            raw=line.rstrip("\n"),
        )


@dataclass(frozen=True, slots=True)
class HilogParseResult:
    events: list[HilogEvent]
    total_lines: int
    parsed: int
    unparsed: int


def parse_hilog_lines(lines: list[str]) -> tuple[list[HilogEvent], list[str]]:
    """Parse a list of hilog text lines. Returns (parsed_events, unparsed_lines)."""
    events: list[HilogEvent] = []
    unparsed: list[str] = []
    for line in lines:
        evt = HilogEvent.parse_line(line)
        if evt:
            events.append(evt)
        else:
            unparsed.append(line.rstrip("\n"))
    return events, unparsed


def parse_hilog_file(path: str | Path) -> HilogParseResult:
    """Parse a hilog text file on disk."""
    path = Path(path)
    logger.info("parsing hilog file: %s", path)
    with open(path) as f:
        lines = f.readlines()
    events, unparsed_lines = parse_hilog_lines(lines)
    result = HilogParseResult(
        events=events,
        total_lines=len(lines),
        parsed=len(events),
        unparsed=len(unparsed_lines),
    )
    logger.info(
        "parsed %s: %d total, %d parsed, %d unparsed",
        path.name,
        result.total_lines,
        result.parsed,
        result.unparsed,
    )
    return result
