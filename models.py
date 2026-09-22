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
