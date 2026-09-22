"""Fixed map-domain values for Fly-in."""

from dataclasses import dataclass
from enum import Enum


class ZoneRole(Enum):
    """Identify a zone's role in a map."""

    START = "start"
    END = "end"
    HUB = "hub"


class ZoneType(Enum):
    """Identify a zone's movement rule."""

    NORMAL = "normal"
    BLOCKED = "blocked"
    RESTRICTED = "restricted"
    PRIORITY = "priority"


@dataclass(frozen=True)
class Zone:
    """Store fixed data and movement facts for one map zone."""

    name: str
    x: int
    y: int
    role: ZoneRole
    zone_type: ZoneType = ZoneType.NORMAL
    color: str = "none"
    max_drones: int = 1

    @property
    def entry_duration(self) -> int:
        """Return the number of turns required to enter this zone."""
        if self.zone_type is ZoneType.RESTRICTED:
            return 2
        return 1

    @property
    def is_blocked(self) -> bool:
        """Return whether this zone cannot be entered."""
        return self.zone_type is ZoneType.BLOCKED


@dataclass(frozen=True)
class Connection:
    """Store one fixed, undirected map connection."""

    zone_a: str
    zone_b: str
    max_link_capacity: int = 1

    @property
    def key(self) -> tuple[str, str]:
        """Return the canonical identity shared by both endpoint orders."""
        if self.zone_a <= self.zone_b:
            return (self.zone_a, self.zone_b)
        return (self.zone_b, self.zone_a)


class GraphError(ValueError):
    """Describe a structural Graph failure and its offending value."""

    def __init__(
        self,
        reason: str,
        subject: Zone | Connection | ZoneRole | None = None,
    ) -> None:
        """Store the stable cause and value needed for source context."""
        self.reason = reason
        self.subject = subject
        super().__init__(reason)
