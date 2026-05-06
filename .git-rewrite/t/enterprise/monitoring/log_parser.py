"""
Log Parser Module - Week 53, Builder 4
Multi-format log parsing
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import re
import json
import logging

logger = logging.getLogger(__name__)


class LogFormat(Enum):
    """Log format types"""
    JSON = "json"
    COMMON = "common"  # Apache common log
    COMBINED = "combined"  # Apache combined log
    SYSLOG = "syslog"
    CUSTOM = "custom"


@dataclass
class ParseResult:
    """Result of log parsing"""
    success: bool
    entry: Optional[Dict[str, Any]] = None
    raw_line: str = ""
    error: Optional[str] = None
    format_used: LogFormat = LogFormat.CUSTOM


class LogParser:
    """
    Parses log lines in various formats.
    """

    def __init__(self):
        self.parsers: Dict[LogFormat, callable] = {}
        self._setup_parsers()

    def _setup_parsers(self) -> None:
        """Setup format parsers"""
        self.parsers[LogFormat.JSON] = self._parse_json
        self.parsers[LogFormat.COMMON] = self._parse_common
        self.parsers[LogFormat.COMBINED] = self._parse_combined
        self.parsers[LogFormat.SYSLOG] = self._parse_syslog

    def parse(
        self,
        line: str,
        format_hint: Optional[LogFormat] = None,
    ) -> ParseResult:
        """Parse a log line"""
        line = line.strip()
        if not line:
            return ParseResult(
                success=False,
                raw_line=line,
                error="Empty line",
            )

        # Try hinted format first
        if format_hint:
            parser = self.parsers.get(format_hint)
            if parser:
                try:
                    entry = parser(line)
                    if entry:
                        return ParseResult(
                            success=True,
                            entry=entry,
                            raw_line=line,
                            format_used=format_hint,
                        )
                except Exception as e:
                    pass

        # Try all formats
        for log_format, parser in self.parsers.items():
            try:
                entry = parser(line)
                if entry:
                    return ParseResult(
                        success=True,
                        entry=entry,
                        raw_line=line,
                        format_used=log_format,
                    )
            except Exception:
                continue

        # Fallback to simple parsing
        return self._parse_simple(line)

    def _parse_json(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse JSON log format"""
        data = json.loads(line)

        # Normalize common fields
        entry = {
            "timestamp": self._extract_timestamp(data),
            "level": data.get("level", data.get("severity", "INFO")),
            "message": data.get("message", data.get("msg", "")),
            "logger": data.get("logger", data.get("name", "")),
            "extra": {k: v for k, v in data.items()
                      if k not in ["timestamp", "level", "message", "logger"]},
        }
        return entry

    def _parse_common(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse Apache common log format"""
        # Example: 127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET / HTTP/1.0" 200 2326
        pattern = r'^(\S+) (\S+) (\S+) \[([^\]]+)\] "(\S+) ([^"]+) (\S+)" (\d+) (\d+)'
        match = re.match(pattern, line)

        if match:
            return {
                "timestamp": self._parse_apache_time(match.group(4)),
                "level": "INFO",
                "message": f"{match.group(5)} {match.group(6)}",
                "source": match.group(1),
                "extra": {
                    "method": match.group(5),
                    "path": match.group(6),
                    "status": int(match.group(8)),
                    "size": int(match.group(9)),
                },
            }
        return None

    def _parse_combined(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse Apache combined log format"""
        # Extended common log with referrer and user-agent
        pattern = r'^(\S+) (\S+) (\S+) \[([^\]]+)\] "(\S+) ([^"]+) (\S+)" (\d+) (\d+) "([^"]*)" "([^"]*)"'
        match = re.match(pattern, line)

        if match:
            return {
                "timestamp": self._parse_apache_time(match.group(4)),
                "level": "INFO",
                "message": f"{match.group(5)} {match.group(6)}",
                "source": match.group(1),
                "extra": {
                    "method": match.group(5),
                    "path": match.group(6),
                    "status": int(match.group(8)),
                    "referrer": match.group(10),
                    "user_agent": match.group(11),
                },
            }
        return None

    def _parse_syslog(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse syslog format"""
        # Example: Jan 10 13:55:36 hostname process[pid]: message
        pattern = r'^(\w{3}\s+\d+\s+\d+:\d+:\d+) (\S+) (\S+?)(?:\[(\d+)\])?: (.*)'
        match = re.match(pattern, line)

        if match:
            return {
                "timestamp": self._parse_syslog_time(match.group(1)),
                "level": "INFO",
                "message": match.group(5),
                "source": match.group(2),
                "logger": match.group(3),
                "extra": {"pid": match.group(4)},
            }
        return None

    def _parse_simple(self, line: str) -> ParseResult:
        """Simple fallback parser"""
        # Try to extract level and message
        level = "INFO"
        for lvl in ["ERROR", "WARNING", "WARN", "INFO", "DEBUG", "CRITICAL"]:
            if line.startswith(lvl) or f"[{lvl}]" in line:
                level = lvl
                break

        return ParseResult(
            success=True,
            entry={
                "timestamp": datetime.utcnow(),
                "level": level,
                "message": line,
            },
            raw_line=line,
            format_used=LogFormat.CUSTOM,
        )

    def _extract_timestamp(self, data: Dict) -> datetime:
        """Extract timestamp from log data"""
        for key in ["timestamp", "time", "@timestamp", "date"]:
            if key in data:
                ts = data[key]
                if isinstance(ts, (int, float)):
                    return datetime.fromtimestamp(ts)
                elif isinstance(ts, str):
                    try:
                        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    except Exception:
                        pass
        return datetime.utcnow()

    def _parse_apache_time(self, time_str: str) -> datetime:
        """Parse Apache log timestamp"""
        try:
            # Example: 10/Oct/2000:13:55:36 -0700
            return datetime.strptime(time_str.split()[0], "%d/%b/%Y:%H:%M:%S")
        except Exception:
            return datetime.utcnow()

    def _parse_syslog_time(self, time_str: str) -> datetime:
        """Parse syslog timestamp"""
        try:
            # Example: Jan 10 13:55:36
            return datetime.strptime(time_str, "%b %d %H:%M:%S")
        except Exception:
            return datetime.utcnow()

    def parse_batch(
        self,
        lines: List[str],
        format_hint: Optional[LogFormat] = None,
    ) -> List[ParseResult]:
        """Parse multiple log lines"""
        return [self.parse(line, format_hint) for line in lines]
