"""Line-level parsing helpers for Fly-in maps."""

from collections.abc import Iterator

from model import Connection, Graph, GraphError, Zone, ZoneRole, ZoneType


class ParseError(ValueError):
    """Describe an input error at a specific source line."""

    def __init__(self, line_number: int, reason: str) -> None:
        """Store the source line and a concise reason for the failure."""
        self.line_number = line_number
        self.reason = reason
        super().__init__(f"Line {line_number}: {reason}")